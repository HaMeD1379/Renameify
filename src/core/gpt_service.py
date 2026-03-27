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


def extract_season_from_path(file_path: str) -> Optional[int]:
    """
    Extract the season number from a file's folder path.
    Supports various naming conventions including British "Series X" format.
    """
    if not file_path:
        return None

    path = Path(file_path)

    for parent in [path.parent] + list(path.parents):
        folder_name = parent.name
        if not folder_name:
            continue

        # Pattern 1: S01, S02, S03
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


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: Optional[dict] = None
) -> str:
    """
    Unified LLM call function that supports multiple providers.

    Returns the raw text response from the LLM.
    """
    if config is None:
        config = load_config()

    provider = config.get("llm_provider", "openai")
    api_key = get_api_key(provider)

    if not api_key:
        raise ValueError(f"API key not configured for provider: {provider}")

    if provider == "openai":
        return _call_openai(system_prompt, user_prompt, config, api_key)
    elif provider == "anthropic":
        return _call_anthropic(system_prompt, user_prompt, config, api_key)
    elif provider == "google":
        return _call_google(system_prompt, user_prompt, config, api_key)
    elif provider == "openrouter":
        return _call_openrouter(system_prompt, user_prompt, config, api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _call_openai(system_prompt: str, user_prompt: str, config: dict, api_key: str) -> str:
    """Call OpenAI API."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key)
    model = config.get("openai_model", "gpt-4o-mini")
    use_web_search = config.get("use_web_search", True)

    try:
        # Try web search if enabled
        if use_web_search and ("gpt-4o" in model or "gpt-4" in model):
            try:
                response = client.responses.create(
                    model=model,
                    tools=[{"type": "web_search_preview"}],
                    input=f"{system_prompt}\n\n{user_prompt}",
                )
                content = ""
                for item in response.output:
                    if hasattr(item, 'content'):
                        for block in item.content:
                            if hasattr(block, 'text'):
                                content += block.text
                return content.strip()
            except (AttributeError, Exception):
                pass  # Fall back to standard chat completion

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=4096
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}")


def _call_anthropic(system_prompt: str, user_prompt: str, config: dict, api_key: str) -> str:
    """Call Anthropic Claude API."""
    if anthropic is None:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)
    model = config.get("anthropic_model", "claude-sonnet-4-20250514")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text.strip()

    except Exception as e:
        raise RuntimeError(f"Anthropic API error: {e}")


def _call_google(system_prompt: str, user_prompt: str, config: dict, api_key: str) -> str:
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
                max_output_tokens=4096
            )
        )
        return response.text.strip()

    except Exception as e:
        raise RuntimeError(f"Google Gemini API error: {e}")


def _call_openrouter(system_prompt: str, user_prompt: str, config: dict, api_key: str) -> str:
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
            max_tokens=4096
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise RuntimeError(f"OpenRouter API error: {e}")


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

    try:
        # Use unified LLM call
        content = call_llm(system_prompt, user_prompt, config)

        # Clean up markdown
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        # Parse JSON
        results = json.loads(content)

        # Convert to MediaInfo objects
        media_infos = []
        for item in results:
            original_fn = item.get("original_filename", "")
            original_path = path_lookup.get(original_fn, "")

            if not original_path:
                for fn, path in path_lookup.items():
                    if fn.lower() == original_fn.lower():
                        original_path = path
                        break
                if not original_path:
                    for fn, path in path_lookup.items():
                        if original_fn in fn or fn in original_fn:
                            original_path = path
                            break

            # Override season from folder path
            extracted_season = extract_season_from_path(original_path)
            gpt_season = item.get("season")
            final_season = extracted_season if extracted_season is not None else gpt_season

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
                notes=item.get("notes")
            )
            media_infos.append(media_info)

        return media_infos

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response: {e}")
    except Exception as e:
        raise RuntimeError(f"LLM API error: {e}")


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
        content = call_llm(system_prompt, user_prompt, config)

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        results = json.loads(content)

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

    batch_size = config.get("gpt_batch_size", 20)
    total_files = len(filenames_with_paths)
    total_batches = (total_files + batch_size - 1) // batch_size
    start_time = time.time()

    batches = []
    for i in range(0, total_files, batch_size):
        batch = filenames_with_paths[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        batches.append((batch_num, batch))

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

        try:
            results = identify_media_batch(batch, config, custom_prompt)
            return batch_num, results, None
        except Exception as e:
            error_results = []
            for fn, path in batch:
                error_results.append(MediaInfo(
                    original_filename=fn,
                    original_path=path,
                    media_type="unknown",
                    title="Unknown",
                    year=None,
                    year_start=None,
                    year_end=None,
                    season=None,
                    episode=None,
                    episode_title=None,
                    confidence=0,
                    notes=f"Error: {str(e)}"
                ))
            return batch_num, error_results, str(e)

    if parallel and total_batches > 1:
        workers = min(max_workers, total_batches)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_batch, batch_info): batch_info
                      for batch_info in batches}

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
        season = info.season or 1
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

        season_template = config.get("season_folder_template", "Season {season:02d}")
        season_folder = season_template.format(season=info.season or 1)

        return f"{series_folder}/{season_folder}"

    return ""
