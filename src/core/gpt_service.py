"""
LLM Service module for Renameify - handles all AI API interactions.

Supports multiple providers:
- OpenAI (GPT-4o, GPT-4, etc.)
- Anthropic (Claude Sonnet 4, Opus 4, Haiku 4)
- Google (Gemini 2.0, 1.5)
- OpenRouter (Any model via unified API)

Features:
- Media file identification (for Plex/Jellyfin/Emby)
- Mass file renaming (generic files)
- Custom prompt overrides
"""
import json
import time
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path

# Try importing different providers
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from .config import load_config, get_api_key, get_custom_prompt, get_current_model

# Use absolute import to work with sys.path setup (both dev and PyInstaller)
try:
    from prompts import get_prompt_manager, MEDIA_SYSTEM_PROMPT, MEDIA_USER_PROMPT
except ImportError:
    # Fallback for relative import if running as package
    from ..prompts import get_prompt_manager, MEDIA_SYSTEM_PROMPT, MEDIA_USER_PROMPT


SPECIALS_FOLDER_NAMES = {
    "specials", "special", "s00",
    "extras", "extra",
    "behind the scenes", "behind_the_scenes", "bts",
    "featurettes", "featurette",
    "interviews", "interview",
    "deleted scenes", "deleted_scenes",
    "shorts", "short films",
    "bonus", "bonus features",
}


def extract_season_from_path(file_path: str) -> Optional[int]:
    """
    Extract the season number from a file's folder path.
    Supports various naming conventions including British "Series X" format.
    Returns 0 for specials/extras folders.
    """
    if not file_path:
        return None

    path = Path(file_path)

    for parent in [path.parent] + list(path.parents):
        folder_name = parent.name
        if not folder_name:
            continue

        # Specials folders -> Season 0
        if folder_name.lower().strip() in SPECIALS_FOLDER_NAMES:
            return 0

        # Pattern 1: S01, S02, S03 (S00 = specials)
        match = re.match(r'^S(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 2: Season 01, Season 1, Season.01
        match = re.match(r'^Season[\s\.]?(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 3: "Show Name S02"
        match = re.search(r'\bS(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 4: "Show Name Season 2"
        match = re.search(r'\bSeason[\s\.]?(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 5: "Series 1", "Series 2" (British TV naming convention)
        match = re.match(r'^Series\s*(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 6: "Show Name Series 2"
        match = re.search(r'\bSeries\s*(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 7: "Staffel X" (German)
        match = re.match(r'^Staffel\s*(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 8: "Temporada X" (Spanish)
        match = re.match(r'^Temporada\s*(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 9: "Saison X" (French)
        match = re.match(r'^Saison\s*(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_special_type_from_path(file_path: str) -> Optional[str]:
    """
    Detect if a file is in a specials/extras folder and return the special type.
    """
    if not file_path:
        return None

    path = Path(file_path)
    for parent in [path.parent] + list(path.parents):
        folder_lower = parent.name.lower().strip()
        if folder_lower in ("specials", "special", "s00"):
            return "special"
        if folder_lower in ("extras", "extra", "bonus", "bonus features"):
            return "special"
        if folder_lower in ("behind the scenes", "behind_the_scenes", "bts"):
            return "behind_the_scenes"
        if folder_lower in ("featurettes", "featurette"):
            return "featurette"
        if folder_lower in ("interviews", "interview"):
            return "interview"
        if folder_lower in ("deleted scenes", "deleted_scenes"):
            return "deleted_scene"
        if folder_lower in ("shorts", "short films"):
            return "short"
    return None


@dataclass
class MediaInfo:
    """Parsed media information from GPT."""
    original_filename: str
    original_path: str
    media_type: str  # "movie", "series", "unknown"
    title: str
    year: Optional[int]
    year_start: Optional[int]
    year_end: Optional[int]
    season: Optional[int]
    episode: Optional[int]
    episode_title: Optional[str]
    confidence: int
    notes: Optional[str]
    special_type: Optional[str] = None  # "special", "interview", "behind_the_scenes", "featurette", "deleted_scene", "short", etc.

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def year_range(self) -> str:
        """Get year range string for series."""
        if self.year_start:
            if self.year_end:
                return f"{self.year_start}-{self.year_end}"
            else:
                return f"{self.year_start}-"
        elif self.year:
            return str(self.year)
        return ""


@dataclass
class RenameInfo:
    """Parsed rename information for generic files."""
    original_filename: str
    new_filename: str
    confidence: int
    notes: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GPTProgress:
    """Progress information during GPT processing."""
    current_batch: int
    total_batches: int
    files_processed: int
    total_files: int
    current_files: List[str]
    elapsed_seconds: float
    estimated_remaining: float
    status: str


def _estimate_max_tokens(file_count: int) -> int:
    """Scale max_tokens based on batch size for reliable complete responses."""
    # ~200 tokens per file in the response (JSON object with all fields)
    # Generous buffer to avoid truncation, especially with web-search context
    base = 1024
    per_file = 200
    return min(base + per_file * file_count, 16384)


def _extract_json_array(content: str) -> list:
    """
    Robustly extract a JSON array from LLM response text.
    Handles markdown fences, leading prose, truncated responses, etc.
    """
    if not content or not content.strip():
        raise ValueError("Empty LLM response")

    # Strip markdown code fences — try each fenced block
    if "```" in content:
        parts = content.split("```")
        for part in parts[1::2]:  # odd-indexed parts are inside fences
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            elif part.startswith("JSON"):
                part = part[4:].strip()
            if part.startswith("["):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    pass

    # Try parsing the whole stripped content
    stripped = content.strip()
    if stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Find the first '[' and last ']' in the text
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try to fix truncated JSON: close any unclosed objects/array
    if start != -1:
        fragment = stripped[start:]
        # Remove trailing comma and whitespace
        fragment = re.sub(r',\s*$', '', fragment)
        if not fragment.endswith("]"):
            # Strategy: find the last complete object (ending with '}') and close the array
            last_complete = fragment.rfind("}")
            if last_complete != -1:
                truncated = fragment[:last_complete + 1]
                # Remove any trailing comma
                truncated = re.sub(r',\s*$', '', truncated)
                # Close the array
                truncated += "]"
                try:
                    result = json.loads(truncated)
                    if isinstance(result, list) and len(result) > 0:
                        return result
                except json.JSONDecodeError:
                    pass

            # Fallback: try aggressive bracket/brace closing
            open_braces = fragment.count("{") - fragment.count("}")
            open_brackets = fragment.count("[") - fragment.count("]")
            # Close any open strings, objects, arrays
            if open_braces > 0:
                fragment += '"' if fragment.rstrip()[-1:] not in ('"', '}', ']', ',') else ''
                fragment += "}" * open_braces
            fragment = re.sub(r',\s*$', '', fragment)
            fragment += "]" * max(open_brackets, 0)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            pass

    # Absolute last resort: try to find individual objects
    salvaged = _salvage_partial_json(content)
    if salvaged:
        return salvaged

    raise ValueError(f"Could not extract JSON array from LLM response:\n{content[:500]}")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: Optional[dict] = None,
    file_count: int = 20
) -> str:
    """
    Unified LLM call function that supports multiple providers.

    Returns the raw text response from the LLM.
    file_count is used to scale max_tokens appropriately.
    """
    if config is None:
        config = load_config()

    provider = config.get("llm_provider", "openai")
    api_key = get_api_key(provider)
    max_tokens = _estimate_max_tokens(file_count)

    if not api_key:
        raise ValueError(f"API key not configured for provider: {provider}")

    if provider == "openai":
        return _call_openai(system_prompt, user_prompt, config, api_key, max_tokens)
    elif provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, config, api_key, max_tokens)
    elif provider == "google":
        return _call_google(system_prompt, user_prompt, config, api_key, max_tokens)
    elif provider == "openrouter":
        return _call_openrouter(system_prompt, user_prompt, config, api_key, max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_openai(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call OpenAI API with web search support and robust error handling."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key, timeout=120.0)
    model = config.get("openai_model", "gpt-4o")
    use_web_search = config.get("use_web_search", True)

    # --- Try Responses API with web search first ---
    if use_web_search:
        last_ws_error = None
        for attempt in range(3):
            try:
                response = client.responses.create(
                    model=model,
                    tools=[{"type": "web_search_preview"}],
                    input=f"{system_prompt}\n\n{user_prompt}",
                    max_output_tokens=max_tokens,
                )
                content = ""
                for output_item in response.output:
                    if hasattr(output_item, 'content'):
                        for block in output_item.content:
                            if hasattr(block, 'text'):
                                content += block.text
                if content.strip():
                    return content.strip()
                # Empty response — fall through to retry or standard
                last_ws_error = "Empty response from web search"
            except Exception as e:
                last_ws_error = e
                err_str = str(e).lower()
                # Rate limit — back off
                if "rate" in err_str or "429" in err_str or "quota" in err_str:
                    wait = 2.0 * (2 ** attempt)
                    time.sleep(wait)
                    continue
                # Timeout — retry once then fall through
                if "timeout" in err_str or "timed out" in err_str:
                    time.sleep(1.0)
                    continue
                # Other error — fall through to standard chat
                break
        # If web search failed, log the reason and try standard completion
        # (don't raise, because we have a fallback)

    # --- Standard Chat Completions API fallback ---
    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=max_tokens
            )
            result = response.choices[0].message.content
            if not result:
                raise RuntimeError("OpenAI returned empty response")
            return result.strip()
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str:
                wait = 2.0 * (2 ** attempt)
                time.sleep(wait)
                continue
            if "timeout" in err_str or "timed out" in err_str:
                time.sleep(1.0)
                continue
            raise RuntimeError(f"OpenAI API error: {e}")

    raise RuntimeError(f"OpenAI API error after retries: {last_error}")


def _call_anthropic(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call Anthropic Claude API."""
    if anthropic is None:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    model = config.get("anthropic_model", "claude-sonnet-4-20250514")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        if not response.content:
            raise RuntimeError("Anthropic returned empty response")
        return response.content[0].text.strip()

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


def _call_google(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call Google Gemini API."""
    if genai is None:
        raise ImportError("Google AI package not installed. Run: pip install google-generativeai")

    genai.configure(api_key=api_key)
    model_name = config.get("google_model", "gemini-2.0-flash")

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt
        )
        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=max_tokens
            )
        )
        if not response.text:
            raise RuntimeError("Google Gemini returned empty response")
        return response.text.strip()

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Google Gemini API error: {e}")


def _call_openrouter(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call OpenRouter API (OpenAI-compatible)."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )
    model = config.get("openrouter_model", "openai/gpt-4o-mini")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=max_tokens
        )
        result = response.choices[0].message.content
        if not result:
            raise RuntimeError("OpenRouter returned empty response")
        return result.strip()

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"OpenRouter API error: {e}")


def _normalize_for_match(name: str) -> str:
    """Normalize a filename for fuzzy matching — lowercase, strip extension, collapse separators."""
    # Remove common extensions
    name = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|mpg|mpeg|ts|m2ts|srt|sub|ass|ssa|vtt)$', '', name, flags=re.IGNORECASE)
    # Replace dots, underscores, dashes with space, lowercase
    name = re.sub(r'[\.\-_]+', ' ', name).lower().strip()
    return name


def _match_filename_to_lookup(original_fn: str, path_lookup: dict) -> str:
    """
    Find the best matching path for a filename returned by the LLM.
    Tries exact match, case-insensitive, stem-only, normalized fuzzy.
    Returns the matched path or empty string.
    """
    if not original_fn:
        return ""

    # 1. Exact match
    if original_fn in path_lookup:
        return path_lookup[original_fn]

    # 2. Case-insensitive exact match
    fn_lower = original_fn.lower()
    for fn, path in path_lookup.items():
        if fn.lower() == fn_lower:
            return path

    # 3. Strip extension from LLM result, match against stems in lookup
    fn_stem = re.sub(r'\.[^.]+$', '', original_fn)
    for fn, path in path_lookup.items():
        lookup_stem = re.sub(r'\.[^.]+$', '', fn)
        if fn_stem.lower() == lookup_stem.lower():
            return path

    # 4. Normalized fuzzy: collapse dots/dashes/underscores, compare
    fn_norm = _normalize_for_match(original_fn)
    for fn, path in path_lookup.items():
        if _normalize_for_match(fn) == fn_norm:
            return path

    # 5. Substring containment (LLM sometimes truncates or extends)
    for fn, path in path_lookup.items():
        fn_l = fn.lower()
        if fn_lower in fn_l or fn_l in fn_lower:
            return path

    return ""


def identify_media_batch(
    filenames_with_paths: List[tuple],
    config: Optional[dict] = None,
    custom_prompt: Optional[str] = None
) -> List[MediaInfo]:
    """
    Send a batch of filenames to the LLM for identification.
    Supports multiple providers (OpenAI, Anthropic Claude, Google Gemini, OpenRouter).
    """
    if config is None:
        config = load_config()

    # Format filenames with their folder paths
    filename_entries = []
    for fn, full_path in filenames_with_paths:
        path_obj = Path(full_path)
        parent_parts = path_obj.parent.parts
        relevant_parts = []
        for part in parent_parts:
            if part in ('\\', '/', '') or (len(part) <= 3 and ':' in part):
                continue
            if part.startswith('\\'):
                continue
            relevant_parts.append(part)
        folder_context = "/".join(relevant_parts[-5:]) if relevant_parts else ""
        filename_entries.append(f"- {fn} | {folder_context}")

    filename_list = "\n".join(filename_entries)
    path_lookup = {fn: path for fn, path in filenames_with_paths}

    # Get prompts (with optional custom override)
    prompt_manager = get_prompt_manager()
    if custom_prompt:
        prompt_manager.set_custom_prompt(custom_prompt)

    system_prompt = prompt_manager.get_media_system_prompt()
    user_prompt = prompt_manager.get_media_user_prompt(filename_list)

    # Call LLM with retry on failure
    content = None
    last_error = None
    for attempt in range(3):
        try:
            content = call_llm(system_prompt, user_prompt, config, file_count=len(filenames_with_paths))
            if content:
                break
        except Exception as e:
            last_error = e
            time.sleep(1.0 * (attempt + 1))

    if not content:
        raise RuntimeError(f"LLM call failed after 3 attempts: {last_error}")

    # Robust JSON extraction
    try:
        results = _extract_json_array(content)
    except ValueError:
        # If JSON extraction totally fails, try to salvage individual objects
        results = _salvage_partial_json(content)

    if not results:
        raise ValueError(f"LLM returned no parseable results. Raw response:\n{content[:500]}")

    # Convert to MediaInfo objects
    media_infos = []
    matched_paths = set()

    for item in results:
        original_fn = item.get("original_filename", "")
        original_path = _match_filename_to_lookup(original_fn, path_lookup)

        if original_path:
            matched_paths.add(original_path)

        # Override season from folder path
        extracted_season = extract_season_from_path(original_path)
        gpt_season = item.get("season")
        final_season = extracted_season if extracted_season is not None else gpt_season

        # Detect special type from folder path (overrides LLM if folder is clearly specials)
        folder_special_type = extract_special_type_from_path(original_path)
        gpt_special_type = item.get("special_type")
        final_special_type = folder_special_type or gpt_special_type or None

        media_info = MediaInfo(
            original_filename=original_fn,
            original_path=original_path,
            media_type=item.get("media_type", "unknown"),
            title=item.get("title", "Unknown"),
            year=item.get("year"),
            year_start=item.get("year_start"),
            year_end=item.get("year_end"),
            season=final_season,
            episode=item.get("episode"),
            episode_title=item.get("episode_title"),
            confidence=item.get("confidence", 0),
            notes=item.get("notes"),
            special_type=final_special_type,
        )
        media_infos.append(media_info)

    # For any input files the LLM missed entirely, create placeholder entries
    for fn, path in filenames_with_paths:
        if path not in matched_paths:
            media_infos.append(MediaInfo(
                original_filename=fn,
                original_path=path,
                media_type="unknown",
                title="Unknown",
                year=None, year_start=None, year_end=None,
                season=None, episode=None, episode_title=None,
                confidence=0,
                notes="LLM did not return a result for this file",
            ))

    return media_infos


def _salvage_partial_json(content: str) -> list:
    """
    Last-resort: find individual JSON objects {...} in the text and collect them into a list.
    """
    results = []
    # Find all top-level { ... } blocks
    depth = 0
    start = None
    for i, ch in enumerate(content):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(content[start:i + 1])
                    if isinstance(obj, dict) and "original_filename" in obj:
                        results.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
    return results


def rename_files_batch(
    filenames: List[str],
    config: Optional[dict] = None,
    custom_prompt: Optional[str] = None
) -> List[RenameInfo]:
    """
    Send a batch of filenames to the LLM for generic rename suggestions.
    Used for mass file renaming mode.
    Supports multiple providers (OpenAI, Anthropic Claude, Google Gemini, OpenRouter).
    """
    if config is None:
        config = load_config()

    prompt_manager = get_prompt_manager()

    if custom_prompt:
        user_prompt = prompt_manager.get_custom_pattern_prompt(
            "\n".join(f"- {fn}" for fn in filenames),
            custom_prompt
        )
    else:
        user_prompt = prompt_manager.get_mass_rename_prompt(
            "\n".join(f"- {fn}" for fn in filenames)
        )

    # For mass rename, we use an empty system prompt and put everything in user prompt
    system_prompt = "You are a file renaming assistant. Return only valid JSON."

    try:
        content = call_llm(system_prompt, user_prompt, config, file_count=len(filenames))

        results = _extract_json_array(content)

        rename_infos = []
        for item in results:
            rename_info = RenameInfo(
                original_filename=item.get("original_filename", ""),
                new_filename=item.get("new_filename", ""),
                confidence=item.get("confidence", 0),
                notes=item.get("notes")
            )
            rename_infos.append(rename_info)

        return rename_infos

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response: {e}")
    except Exception as e:
        raise RuntimeError(f"LLM API error: {e}")


def identify_all_media(
    filenames_with_paths: List[tuple],
    config: Optional[dict] = None,
    progress_callback: Optional[Callable[[GPTProgress], None]] = None,
    parallel: bool = True,
    max_workers: int = 3,
    custom_prompt: Optional[str] = None
) -> List[MediaInfo]:
    """
    Identify all media files with batching and parallel processing.
    """
    if config is None:
        config = load_config()

    batch_size = config.get("gpt_batch_size", 15)
    total_files = len(filenames_with_paths)
    start_time = time.time()

    # Group files by parent folder so the LLM gets full series context per batch
    folder_groups = {}
    for fn, path in filenames_with_paths:
        parent = str(Path(path).parent)
        folder_groups.setdefault(parent, []).append((fn, path))

    # Build batches respecting folder grouping (keep same-folder files together)
    batches = []
    current_batch = []
    for folder_files in folder_groups.values():
        for item in folder_files:
            current_batch.append(item)
            if len(current_batch) >= batch_size:
                batches.append((len(batches) + 1, current_batch))
                current_batch = []
    if current_batch:
        batches.append((len(batches) + 1, current_batch))

    total_batches = len(batches)

    results_lock = threading.Lock()
    all_results = [None] * total_batches
    completed_batches = [0]

    def process_batch(batch_info):
        batch_num, batch = batch_info
        batch_filenames = [fn for fn, _ in batch]

        if progress_callback:
            elapsed = time.time() - start_time
            avg_time = elapsed / max(completed_batches[0], 1) if completed_batches[0] > 0 else 5
            remaining = avg_time * (total_batches - completed_batches[0])

            progress = GPTProgress(
                current_batch=batch_num,
                total_batches=total_batches,
                files_processed=completed_batches[0] * batch_size,
                total_files=total_files,
                current_files=batch_filenames[:3],
                elapsed_seconds=elapsed,
                estimated_remaining=remaining,
                status="processing"
            )
            progress_callback(progress)

        # Try full batch, then retry with smaller splits on failure
        last_error = None
        for attempt in range(3):
            try:
                results = identify_media_batch(batch, config, custom_prompt)
                return batch_num, results, None
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Exponential backoff for rate limits
                if "rate" in err_str or "429" in err_str or "quota" in err_str:
                    time.sleep(3.0 * (2 ** attempt))
                else:
                    time.sleep(1.5 * (attempt + 1))

        # Full batch failed — split into thirds (or halves for small batches)
        if len(batch) > 2:
            chunk_size = max(1, len(batch) // 3) if len(batch) > 6 else max(1, len(batch) // 2)
            chunks = [batch[i:i + chunk_size] for i in range(0, len(batch), chunk_size)]
            combined_results = []
            for chunk in chunks:
                for retry in range(2):
                    try:
                        chunk_results = identify_media_batch(chunk, config, custom_prompt)
                        combined_results.extend(chunk_results)
                        break
                    except Exception as chunk_err:
                        last_error = chunk_err
                        if retry == 0:
                            time.sleep(2.0)
                        else:
                            # This chunk also failed — create error entries
                            for fn, path in chunk:
                                combined_results.append(MediaInfo(
                                    original_filename=fn,
                                    original_path=path,
                                    media_type="unknown",
                                    title="Unknown",
                                    year=None, year_start=None, year_end=None,
                                    season=None, episode=None, episode_title=None,
                                    confidence=0,
                                    notes=f"Error: {str(chunk_err)}"
                                ))
                # Small delay between chunk calls to avoid rate limits
                time.sleep(0.5)
            return batch_num, combined_results, str(last_error)

        # Single file batch still failed
        error_results = []
        for fn, path in batch:
            error_results.append(MediaInfo(
                original_filename=fn,
                original_path=path,
                media_type="unknown",
                title="Unknown",
                year=None, year_start=None, year_end=None,
                season=None, episode=None, episode_title=None,
                confidence=0,
                notes=f"Error: {str(last_error)}"
            ))
        return batch_num, error_results, str(last_error)

    if parallel and total_batches > 1:
        # Use fewer workers when web search is enabled (more resource-intensive calls)
        use_web = config.get("use_web_search", True)
        effective_workers = min(2 if use_web else max_workers, total_batches)

        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {}
            for i, batch_info in enumerate(batches):
                futures[executor.submit(process_batch, batch_info)] = batch_info
                # Stagger submissions slightly to avoid simultaneous rate-limit hits
                if i < len(batches) - 1:
                    time.sleep(0.3)

            for future in as_completed(futures):
                batch_num, results, error = future.result()

                with results_lock:
                    all_results[batch_num - 1] = results
                    completed_batches[0] += 1

                if progress_callback:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / completed_batches[0]
                    remaining = avg_time * (total_batches - completed_batches[0])

                    progress = GPTProgress(
                        current_batch=completed_batches[0],
                        total_batches=total_batches,
                        files_processed=completed_batches[0] * batch_size,
                        total_files=total_files,
                        current_files=[],
                        elapsed_seconds=elapsed,
                        estimated_remaining=remaining,
                        status="processing" if completed_batches[0] < total_batches else "complete"
                    )
                    progress_callback(progress)
    else:
        for batch_info in batches:
            batch_num, results, error = process_batch(batch_info)
            all_results[batch_num - 1] = results
            completed_batches[0] += 1

            if progress_callback:
                elapsed = time.time() - start_time
                avg_time = elapsed / completed_batches[0] if completed_batches[0] > 0 else 5
                remaining = avg_time * (total_batches - completed_batches[0])

                progress = GPTProgress(
                    current_batch=completed_batches[0],
                    total_batches=total_batches,
                    files_processed=completed_batches[0] * batch_size,
                    total_files=total_files,
                    current_files=[],
                    elapsed_seconds=elapsed,
                    estimated_remaining=remaining,
                    status="processing" if completed_batches[0] < total_batches else "complete"
                )
                progress_callback(progress)

            if batch_num < total_batches:
                time.sleep(0.3)

    final_results = []
    for batch_results in all_results:
        if batch_results:
            final_results.extend(batch_results)

    if progress_callback:
        progress = GPTProgress(
            current_batch=total_batches,
            total_batches=total_batches,
            files_processed=total_files,
            total_files=total_files,
            current_files=[],
            elapsed_seconds=time.time() - start_time,
            estimated_remaining=0,
            status="complete"
        )
        progress_callback(progress)

    return final_results


def format_media_info(info: MediaInfo, config: Optional[dict] = None) -> str:
    """Format MediaInfo into the target filename."""
    if config is None:
        config = load_config()

    if info.media_type == "movie":
        if info.year:
            template = config.get("movie_file_template", "{title} [{year}]")
            return template.format(title=info.title, year=info.year)
        else:
            return info.title

    elif info.media_type == "series":
        season = info.season if info.season is not None else 1
        episode = info.episode or 1

        episode_title = info.episode_title
        if episode_title:
            import re
            generic_patterns = [
                r'^Episode\s*\d*$',
                r'^Episodio\s*\d*$',
                r'^Episode\s+\d+$',
                r'^Ep\s*\d+$',
                r'^E\d+$',
            ]
            for pattern in generic_patterns:
                if re.match(pattern, episode_title, re.IGNORECASE):
                    episode_title = None
                    break

        if episode_title:
            template = config.get("episode_file_template", "{series} S{season:02d}E{episode:02d} - {episode_title}")
            return template.format(
                series=info.title,
                season=season,
                episode=episode,
                episode_title=episode_title
            )
        else:
            return f"{info.title} S{season:02d}E{episode:02d}"

    return info.original_filename


def format_folder_structure(info: MediaInfo, config: Optional[dict] = None) -> str:
    """Get the target folder structure for a media file."""
    if config is None:
        config = load_config()

    if info.media_type == "movie":
        if info.year:
            template = config.get("movie_folder_template", "{title} [{year}]")
            return template.format(title=info.title, year=info.year)
        else:
            return info.title

    elif info.media_type == "series":
        year_range = info.year_range

        if year_range:
            template = config.get("series_folder_template", "{series} [{year_range}]")
            series_folder = template.format(series=info.title, year_range=year_range)
        else:
            series_folder = info.title

        season = info.season if info.season is not None else 1
        if season == 0:
            # Specials go into a "Specials" folder (standard for Plex/Jellyfin/Emby)
            season_folder = "Specials"
        else:
            season_template = config.get("season_folder_template", "Season {season:02d}")
            season_folder = season_template.format(season=season)

        return f"{series_folder}/{season_folder}"

    return ""
