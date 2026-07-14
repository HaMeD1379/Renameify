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
- Cancellation support
"""
import json
import time
import re
import warnings
import importlib
from typing import List, Optional, Callable
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
    from google import genai as google_genai
    from google.genai import types as google_genai_types
except ImportError:
    google_genai = None
    google_genai_types = None

from .config import (
    PLEX_AGENT_OPTIONS,
    PLEX_EPISODE_ORDERING_OPTIONS,
    PLEX_SCANNER_OPTIONS,
    load_config,
    get_api_key,
    get_current_model,
    normalize_plex_options,
)

# Use absolute import to work with sys.path setup (both dev and PyInstaller)
try:
    from prompts import get_prompt_manager, MEDIA_SYSTEM_PROMPT, MEDIA_USER_PROMPT
except ImportError:
    # Fallback for relative import if running as package
    from ..prompts import get_prompt_manager, MEDIA_SYSTEM_PROMPT, MEDIA_USER_PROMPT


# Global cancellation event — set by the GUI to abort in-flight LLM work
_cancel_event = threading.Event()
_cancel_generation = 0
_cancel_lock = threading.Lock()
_thread_state = threading.local()


def bind_cancel_token(token: Optional[int]) -> None:
    """Bind a cancellation token to the current thread."""
    _thread_state.cancel_token = token


def get_cancel_token() -> Optional[int]:
    """Get the cancellation token bound to the current thread, if any."""
    return getattr(_thread_state, "cancel_token", None)


def request_cancel():
    """Signal all running LLM operations to stop."""
    _cancel_event.set()


def reset_cancel() -> int:
    """Start a fresh cancellation generation and return its token."""
    global _cancel_generation
    with _cancel_lock:
        _cancel_generation += 1
        _cancel_event.clear()
        return _cancel_generation


def is_cancelled(token: Optional[int] = None) -> bool:
    """Check if cancellation has been requested for the current or specified token."""
    active_token = get_cancel_token() if token is None else token
    if active_token is not None and active_token != _cancel_generation:
        return True
    return _cancel_event.is_set()


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
        match = re.match(r'^Season[\s.]?(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 3: "Show Name S02"
        match = re.search(r'\bS(\d{1,2})$', folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 4: "Show Name Season 2"
        match = re.search(r'\bSeason[\s.]?(\d{1,2})$', folder_name, re.IGNORECASE)
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
    special_type: Optional[str] = None

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
    """Scale max_tokens based on batch size for reliable complete responses.
    
    Optimized: use tighter estimates to reduce wasted tokens while
    still leaving headroom for web-search context.
    """
    # ~150 tokens per file in the response (JSON object with all fields)
    # Add buffer for formatting overhead
    base = 512
    per_file = 180
    return min(base + per_file * file_count, 12288)


def _sleep_with_cancel(duration: float, step: float = 0.1, token: Optional[int] = None) -> None:
    """Sleep in short increments so cancellation is respected quickly."""
    deadline = time.time() + max(duration, 0)
    while time.time() < deadline:
        if is_cancelled(token):
            raise InterruptedError("Operation cancelled")
        time.sleep(min(step, max(deadline - time.time(), 0)))


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
    Raises CancelledError if cancellation was requested.
    """
    if is_cancelled():
        raise InterruptedError("Operation cancelled")

    if config is None:
        config = load_config()

    provider = config.get("llm_provider", "openai")
    api_key = config.get(f"{provider}_api_key") or get_api_key(provider)
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


def test_llm_connection(
    provider: str,
    api_key: str,
    model_name: Optional[str] = None,
    base_config: Optional[dict] = None,
) -> dict:
    """Run a lightweight provider test using the same LLM pipeline as production calls."""
    config = dict(base_config or load_config())
    config["llm_provider"] = provider
    config[f"{provider}_api_key"] = api_key.strip()

    model_key = f"{provider}_model"
    if model_name:
        config[model_key] = model_name

    resolved_model = config.get(model_key) or get_current_model()
    require_web_search = bool(config.get("require_web_search", False))

    if provider == "openai" and (require_web_search or config.get("use_web_search", True)):
        return _test_openai_web_search_connection(api_key, resolved_model)

    if require_web_search:
        raise ValueError("Internet-access model testing is currently supported for OpenAI only.")

    # Keep test calls lightweight and deterministic.
    if provider == "openai":
        config["use_web_search"] = False

    system_prompt = "You are a connection test assistant. Return only valid JSON."
    user_prompt = (
        "Return only this JSON array with no markdown or extra text: "
        f"[{{\"status\":\"ok\",\"provider\":\"{provider}\",\"model\":\"{resolved_model}\"}}]"
    )

    content = call_llm(system_prompt, user_prompt, config=config, file_count=1)
    results = _extract_json_array(content)
    if not results or not isinstance(results[0], dict):
        raise ValueError("Provider responded, but the response format was not valid JSON.")

    first = results[0]
    if first.get("status") != "ok":
        raise ValueError(f"Unexpected validation payload: {first}")

    return {
        "provider": provider,
        "model": first.get("model") or resolved_model,
        "parsed": first,
        "raw_response": content,
    }


def _extract_openai_response_text(response) -> str:
    """Extract text from an OpenAI Responses API result across SDK shapes."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    content = ""
    for output_item in getattr(response, "output", []) or []:
        blocks = getattr(output_item, "content", None)
        if not blocks and isinstance(output_item, dict):
            blocks = output_item.get("content")
        for block in blocks or []:
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                content += text
    return content.strip()


def _openai_response_used_web_search(response) -> bool:
    for output_item in getattr(response, "output", []) or []:
        item_type = getattr(output_item, "type", None)
        if item_type is None and isinstance(output_item, dict):
            item_type = output_item.get("type")
        if item_type and "web_search" in str(item_type):
            return True
    return False


def _test_openai_web_search_connection(api_key: str, model: str) -> dict:
    """Verify that the selected OpenAI model can run the Responses web search tool."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")
    if not api_key or not api_key.strip():
        raise ValueError("API key not configured for provider: openai")

    client = OpenAI(api_key=api_key.strip(), timeout=60.0)
    prompt = (
        "Use the web search tool once to verify internet access. "
        "Then return only this JSON array with no markdown or extra text: "
        f"[{{\"status\":\"ok\",\"provider\":\"openai\",\"model\":\"{model}\",\"web_search\":true}}]"
    )

    last_error = None
    for attempt in range(2):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
        try:
            response = client.responses.create(
                model=model,
                tools=[{"type": "web_search_preview"}],
                input=prompt,
                max_output_tokens=320,
            )
            content = _extract_openai_response_text(response)
            if not content:
                raise RuntimeError("OpenAI returned an empty web-search test response")
            if not _openai_response_used_web_search(response):
                raise RuntimeError("OpenAI did not report a web_search call for this model")

            results = _extract_json_array(content)
            if not results or not isinstance(results[0], dict):
                raise ValueError("OpenAI responded, but the validation JSON was invalid.")
            first = results[0]
            if first.get("status") != "ok":
                raise ValueError(f"Unexpected validation payload: {first}")

            return {
                "provider": "openai",
                "model": first.get("model") or model,
                "web_search": True,
                "parsed": first,
                "raw_response": content,
            }
        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str:
                _sleep_with_cancel(2.0 * (2 ** attempt))
                continue
            if "timeout" in err_str or "timed out" in err_str:
                _sleep_with_cancel(1.0)
                continue
            break

    raise RuntimeError(f"OpenAI web-search test failed for {model}: {last_error}")


def _call_openai(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call OpenAI API with web search support and robust error handling."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key, timeout=90.0)
    model = config.get("openai_model", "gpt-4o-mini")
    use_web_search = config.get("use_web_search", True)
    require_web_search = bool(config.get("require_web_search", False))

    # --- Try Responses API with web search first ---
    if use_web_search:
        last_ws_error = None
        for attempt in range(3):
            if is_cancelled():
                raise InterruptedError("Operation cancelled")
            try:
                response = client.responses.create(
                    model=model,
                    tools=[{"type": "web_search_preview"}],
                    input=f"{system_prompt}\n\n{user_prompt}",
                    max_output_tokens=max_tokens,
                )
                content = _extract_openai_response_text(response)
                if content.strip():
                    return content.strip()
                last_ws_error = "Empty response from web search"
            except Exception as e:
                last_ws_error = e
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str or "quota" in err_str:
                    wait = 2.0 * (2 ** attempt)
                    _sleep_with_cancel(wait)
                    continue
                if "timeout" in err_str or "timed out" in err_str:
                    _sleep_with_cancel(1.0)
                    continue
                break

        if require_web_search:
            raise RuntimeError(f"OpenAI web search failed for {model}: {last_ws_error}")

    # --- Standard Chat Completions API fallback ---
    last_error = None
    for attempt in range(3):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
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
        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str:
                wait = 2.0 * (2 ** attempt)
                _sleep_with_cancel(wait)
                continue
            if "timeout" in err_str or "timed out" in err_str:
                _sleep_with_cancel(1.0)
                continue
            raise RuntimeError(f"OpenAI API error: {e}")

    raise RuntimeError(f"OpenAI API error after retries: {last_error}")


def _call_anthropic(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call Anthropic Claude API with retry logic."""
    if anthropic is None:
        raise ImportError("Anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
    model = config.get("anthropic_model", "claude-sonnet-4-20250514")

    last_error = None
    for attempt in range(3):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
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

        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "overloaded" in err_str:
                wait = 2.0 * (2 ** attempt)
                _sleep_with_cancel(wait)
                continue
            if "timeout" in err_str or "timed out" in err_str:
                _sleep_with_cancel(1.0)
                continue
            raise RuntimeError(f"Anthropic API error: {e}")

    raise RuntimeError(f"Anthropic API error after retries: {last_error}")


def _get_google_sdk():
    """Return the available Google SDK implementation, preferring google-genai."""
    if google_genai is not None and google_genai_types is not None:
        return "google-genai", google_genai, google_genai_types

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            legacy_genai = importlib.import_module("google.generativeai")
        return "google-generativeai", legacy_genai, None
    except ImportError:
        return None, None, None


def _extract_google_response_text(response) -> str:
    """Extract plain text from either Google SDK response shape."""
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    candidates = getattr(response, "candidates", None) or []
    parts = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text.strip())

    return "\n".join(part for part in parts if part).strip()


def call_google_text(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model_name: str,
    max_tokens: int = 4096,
    temperature: float = 0.1,
    timeout: int = 90,
) -> str:
    """Generate text with Gemini using google-genai when available, else the legacy SDK."""
    sdk_name, sdk_module, sdk_types = _get_google_sdk()

    if sdk_module is None:
        raise ImportError("Google AI package not installed. Run: pip install google-genai")

    if sdk_name == "google-genai":
        client = sdk_module.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=sdk_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        text = _extract_google_response_text(response)
        if not text:
            raise RuntimeError("Google Gemini returned empty response")
        return text

    sdk_module.configure(api_key=api_key)
    model = sdk_module.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt
    )
    response = model.generate_content(
        user_prompt,
        generation_config=sdk_module.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        ),
        request_options={"timeout": timeout}
    )
    text = _extract_google_response_text(response)
    if not text:
        raise RuntimeError("Google Gemini returned empty response")
    return text


def _call_google(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call Google Gemini API with retry logic."""
    model_name = config.get("google_model", "gemini-2.0-flash")

    last_error = None
    for attempt in range(3):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
        try:
            return call_google_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                api_key=api_key,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=0.1,
                timeout=90,
            )

        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str or "resource" in err_str:
                wait = 2.0 * (2 ** attempt)
                _sleep_with_cancel(wait)
                continue
            if "timeout" in err_str or "timed out" in err_str or "deadline" in err_str:
                _sleep_with_cancel(1.0)
                continue
            raise RuntimeError(f"Google Gemini API error: {e}")

    raise RuntimeError(f"Google Gemini API error after retries: {last_error}")


def _call_openrouter(system_prompt: str, user_prompt: str, config: dict, api_key: str, max_tokens: int = 4096) -> str:
    """Call OpenRouter API (OpenAI-compatible) with retry logic."""
    if OpenAI is None:
        raise ImportError("OpenAI package not installed. Run: pip install openai")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=90.0
    )
    model = config.get("openrouter_model", "openai/gpt-4o-mini")

    last_error = None
    for attempt in range(3):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
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

        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "quota" in err_str:
                wait = 2.0 * (2 ** attempt)
                _sleep_with_cancel(wait)
                continue
            if "timeout" in err_str or "timed out" in err_str:
                _sleep_with_cancel(1.0)
                continue
            raise RuntimeError(f"OpenRouter API error: {e}")

    raise RuntimeError(f"OpenRouter API error after retries: {last_error}")


def _normalize_for_match(name: str) -> str:
    """Normalize a filename for fuzzy matching — lowercase, strip extension, collapse separators."""
    name = re.sub(r'\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|mpg|mpeg|ts|m2ts|srt|sub|ass|ssa|vtt)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[._-]+', ' ', name).lower().strip()
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


def _plex_library_context(config: dict) -> str:
    """Return compact Plex-specific identification hints based on selected options."""
    if config.get("platform") != "plex" or not config.get("plex_options_enabled"):
        return ""

    normalize_plex_options(config)
    scanner_key = config.get("plex_scanner", "auto")
    agent_key = config.get("plex_agent", "auto")
    ordering_key = config.get("plex_episode_ordering", "tmdb_aired")
    scanner = PLEX_SCANNER_OPTIONS.get(scanner_key, PLEX_SCANNER_OPTIONS["auto"])
    agent = PLEX_AGENT_OPTIONS.get(agent_key, PLEX_AGENT_OPTIONS["auto"])
    ordering = PLEX_EPISODE_ORDERING_OPTIONS.get(ordering_key, "The Movie Database (Aired)")

    lines = [
        "PLEX LIBRARY OPTIONS:",
        f"- Scanner: {scanner['name']}",
        f"- Agent: {agent['name']}",
    ]

    scanner_type = scanner.get("library_type")
    if scanner_type == "movie":
        lines.append("- Treat this as a Plex movie library. Prefer media_type=\"movie\" for feature films and media_type=\"unknown\" for TV episode-style files, because Plex movie scanners ignore TV episodes.")
        lines.append("- Use Plex movie naming: Movie Name (Year), with the year when known.")
    elif scanner_type == "series":
        lines.append("- Treat this as a Plex TV library. Prefer media_type=\"series\" for episodic/date-based content and media_type=\"unknown\" for standalone movie files.")
        lines.append("- Use the English word \"Season\" for season directories; Specials are season 0.")
        lines.append(f"- Episode ordering preference: {ordering}. Use that source/order when identifying episode numbers and titles.")
    elif scanner_type == "other":
        lines.append("- Treat this as personal/other video content. Only return movie or series when the file clearly matches an online title; otherwise return media_type=\"unknown\".")

    agent_type = agent.get("library_type")
    if agent_type == "movie":
        lines.append("- The selected Plex agent is movie-oriented; do not classify TV episodes as movies.")
    elif agent_type == "series":
        lines.append("- The selected Plex agent is series-oriented; include series year when known and use SxxExx episode matching.")
    elif agent_type == "other":
        lines.append("- The selected Plex agent is personal-media-oriented; avoid inventing online metadata for ambiguous files.")

    return "\n".join(lines)


def _apply_plex_scanner_rules(item: dict, config: dict) -> tuple[str, Optional[str]]:
    """Apply Plex scanner library-type rules after model output."""
    media_type = item.get("media_type", "unknown")
    note = item.get("notes")
    if config.get("platform") != "plex" or not config.get("plex_options_enabled"):
        return media_type, note

    normalize_plex_options(config)
    scanner = PLEX_SCANNER_OPTIONS.get(config.get("plex_scanner", "auto"), PLEX_SCANNER_OPTIONS["auto"])
    scanner_type = scanner.get("library_type")
    if scanner_type == "movie" and media_type == "series":
        reason = "Skipped because the selected Plex movie scanner ignores TV episode-style content."
        return "unknown", f"{note}; {reason}" if note else reason
    if scanner_type == "series" and media_type == "movie":
        reason = "Skipped because the selected Plex TV Series scanner expects episodic TV content."
        return "unknown", f"{note}; {reason}" if note else reason
    if scanner_type == "other" and media_type not in {"movie", "series"}:
        return "unknown", note
    return media_type, note


def identify_media_batch(
    filenames_with_paths: List[tuple],
    config: Optional[dict] = None,
    custom_prompt: Optional[str] = None
) -> List[MediaInfo]:
    """
    Send a batch of filenames to the LLM for identification.
    Supports multiple providers (OpenAI, Anthropic Claude, Google Gemini, OpenRouter).
    """
    if is_cancelled():
        raise InterruptedError("Operation cancelled")

    if config is None:
        config = load_config()

    # Format filenames with their folder paths — compact format to save tokens
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
        # Only include the last 3 path components to reduce tokens
        folder_context = "/".join(relevant_parts[-3:]) if relevant_parts else ""
        filename_entries.append(f"- {fn} | {folder_context}")

    filename_list = "\n".join(filename_entries)
    path_lookup = {fn: path for fn, path in filenames_with_paths}

    # Get prompts (with optional custom override)
    prompt_manager = get_prompt_manager()
    if custom_prompt:
        prompt_manager.set_custom_prompt(custom_prompt)
    else:
        prompt_manager.clear_custom_prompt()

    system_prompt = prompt_manager.get_media_system_prompt()
    plex_context = _plex_library_context(config)
    if plex_context:
        system_prompt = f"{system_prompt}\n\n{plex_context}"
    user_prompt = prompt_manager.get_media_user_prompt(filename_list)

    # Call LLM with retry on failure
    content = None
    last_error = None
    for attempt in range(3):
        if is_cancelled():
            raise InterruptedError("Operation cancelled")
        try:
            content = call_llm(system_prompt, user_prompt, config, file_count=len(filenames_with_paths))
            if content:
                break
        except InterruptedError:
            raise
        except Exception as e:
            last_error = e
            _sleep_with_cancel(1.0 * (attempt + 1))

    if not content:
        raise RuntimeError(f"LLM call failed after 3 attempts: {last_error}")

    # Robust JSON extraction
    try:
        results = _extract_json_array(content)
    except ValueError:
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

        media_type, notes = _apply_plex_scanner_rules(item, config)

        # Override season from folder path
        extracted_season = extract_season_from_path(original_path)
        gpt_season = item.get("season")
        final_season = extracted_season if extracted_season is not None else gpt_season

        # Detect special type from folder path (overrides LLM if folder is clearly specials)
        folder_special_type = extract_special_type_from_path(original_path)
        gpt_special_type = item.get("special_type")
        final_special_type = folder_special_type or gpt_special_type or None
        final_episode = item.get("episode")
        final_episode_title = item.get("episode_title")

        # Movies are never TV specials. Folder-derived season/special hints are
        # useful for series, but they can misclassify standalone movies stored in
        # folders named "Specials", "Extras", or similar.
        if media_type == "movie":
            final_season = None
            final_episode = None
            final_episode_title = None
            final_special_type = None

        media_info = MediaInfo(
            original_filename=original_fn,
            original_path=original_path,
            media_type=media_type,
            title=item.get("title", "Unknown"),
            year=item.get("year"),
            year_start=item.get("year_start"),
            year_end=item.get("year_end"),
            season=final_season,
            episode=final_episode,
            episode_title=final_episode_title,
            confidence=item.get("confidence", 0),
            notes=notes,
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
    """
    if is_cancelled():
        raise InterruptedError("Operation cancelled")

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
    except InterruptedError:
        raise
    except Exception as e:
        raise RuntimeError(f"LLM API error: {e}")


def identify_all_media(
    filenames_with_paths: List[tuple],
    config: Optional[dict] = None,
    progress_callback: Optional[Callable[[GPTProgress], None]] = None,
    parallel: bool = True,
    max_workers: int = 3,
    custom_prompt: Optional[str] = None,
    cancel_token: Optional[int] = None,
) -> List[MediaInfo]:
    """
    Identify all media files with batching and parallel processing.
    Supports cancellation via request_cancel().
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
        bind_cancel_token(cancel_token)
        batch_num, batch = batch_info
        batch_filenames = [fn for fn, _ in batch]

        if is_cancelled():
            return batch_num, [], "Cancelled"

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
                status=f"Batch {batch_num}/{total_batches}"
            )
            progress_callback(progress)

        # Try full batch, then retry with smaller splits on failure
        last_error = None
        for attempt in range(3):
            if is_cancelled():
                return batch_num, [], "Cancelled"
            try:
                results = identify_media_batch(batch, config, custom_prompt)
                return batch_num, results, None
            except InterruptedError:
                return batch_num, [], "Cancelled"
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str or "quota" in err_str:
                    _sleep_with_cancel(3.0 * (2 ** attempt))
                else:
                    _sleep_with_cancel(1.5 * (attempt + 1))

        # Full batch failed — split into smaller chunks
        if is_cancelled():
            return batch_num, [], "Cancelled"

        if len(batch) > 2:
            chunk_size = max(1, len(batch) // 3) if len(batch) > 6 else max(1, len(batch) // 2)
            chunks = [batch[i:i + chunk_size] for i in range(0, len(batch), chunk_size)]
            combined_results = []
            for chunk in chunks:
                if is_cancelled():
                    return batch_num, combined_results, "Cancelled"
                for retry in range(2):
                    if is_cancelled():
                        return batch_num, combined_results, "Cancelled"
                    try:
                        chunk_results = identify_media_batch(chunk, config, custom_prompt)
                        combined_results.extend(chunk_results)
                        break
                    except InterruptedError:
                        return batch_num, combined_results, "Cancelled"
                    except Exception as chunk_err:
                        last_error = chunk_err
                        if retry == 0:
                            _sleep_with_cancel(2.0)
                        else:
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
                _sleep_with_cancel(0.5)
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
        use_web = config.get("use_web_search", True)
        effective_workers = min(2 if use_web else max_workers, total_batches)

        executor = ThreadPoolExecutor(max_workers=effective_workers)
        try:
            futures = {}
            for i, batch_info in enumerate(batches):
                if is_cancelled():
                    break
                futures[executor.submit(process_batch, batch_info)] = batch_info
                if i < len(batches) - 1:
                    _sleep_with_cancel(0.3)

            for future in as_completed(futures):
                if is_cancelled():
                    for f in futures:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

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
                        status=f"Batch {completed_batches[0]}/{total_batches}" if completed_batches[0] < total_batches else "complete"
                    )
                    progress_callback(progress)
        finally:
            executor.shutdown(wait=not is_cancelled(), cancel_futures=is_cancelled())
    else:
        for batch_info in batches:
            if is_cancelled():
                break

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
                    status=f"Batch {completed_batches[0]}/{total_batches}" if completed_batches[0] < total_batches else "complete"
                )
                progress_callback(progress)

            if batch_num < total_batches:
                _sleep_with_cancel(0.3)

    final_results = []
    for batch_results in all_results:
        if batch_results:
            final_results.extend(batch_results)

    if progress_callback:
        status = "cancelled" if is_cancelled() else "complete"
        progress = GPTProgress(
            current_batch=total_batches,
            total_batches=total_batches,
            files_processed=total_files,
            total_files=total_files,
            current_files=[],
            elapsed_seconds=time.time() - start_time,
            estimated_remaining=0,
            status=status
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
            season_folder = "Specials"
        else:
            season_template = config.get("season_folder_template", "Season {season:02d}")
            season_folder = season_template.format(season=season)

        return f"{series_folder}/{season_folder}"

    return ""
