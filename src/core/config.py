"""
Configuration module for Renameify - AI-Powered File Renaming Tool.

Config file is stored in Windows Documents/Renameify folder for portability.
The application can be run from anywhere and will always find its config.

Supports multiple platforms:
- Plex (with Agent/Scanner options)
- Jellyfin
- Emby
- Generic (custom naming)
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import Optional

APP_NAME = "Renameify"
APP_VERSION = "2.1.1"
__version__ = APP_VERSION
__app_name__ = APP_NAME
CONFIG_FILENAME = "renameify_config.json"

# Platform presets
PLATFORM_PLEX = "plex"
PLATFORM_JELLYFIN = "jellyfin"
PLATFORM_EMBY = "emby"
PLATFORM_GENERIC = "generic"

# Plex Agent/Scanner options
PLEX_AGENT_PLEX_MOVIE = "com.plexapp.agents.imdb"  # Plex Movie
PLEX_AGENT_PLEX_SERIES = "com.plexapp.agents.thetvdb"  # Plex Series
PLEX_AGENT_TMDB = "tv.plex.agents.movie"  # The Movie Database
PLEX_SCANNER_PLEX_MOVIE = "Plex Movie"
PLEX_SCANNER_PLEX_SERIES = "Plex TV Series"


def get_documents_dir() -> Path:
    """Get the Windows Documents directory."""
    # Try to get from environment
    if sys.platform == "win32":
        import ctypes.wintypes
        CSIDL_PERSONAL = 5  # Documents folder
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf)
        if buf.value:
            return Path(buf.value)

    # Fallback to home directory
    return Path.home() / "Documents"


def get_config_dir() -> Path:
    """
    Get the Renameify config directory in Windows Documents.
    Creates the directory if it doesn't exist.
    """
    config_dir = get_documents_dir() / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / CONFIG_FILENAME


def get_logs_dir() -> Path:
    """Get the logs directory for rename operations."""
    logs_dir = get_config_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


# Platform-specific naming templates
PLATFORM_TEMPLATES = {
    PLATFORM_PLEX: {
        "movie_folder_template": "{title} ({year})",
        "movie_file_template": "{title} ({year})",
        "series_folder_template": "{series} ({year_range})",
        "season_folder_template": "Season {season:02d}",
        "episode_file_template": "{series} - S{season:02d}E{episode:02d} - {episode_title}",
    },
    PLATFORM_JELLYFIN: {
        "movie_folder_template": "{title} ({year})",
        "movie_file_template": "{title} ({year})",
        "series_folder_template": "{series} ({year_range})",
        "season_folder_template": "Season {season:02d}",
        "episode_file_template": "{series} S{season:02d}E{episode:02d} {episode_title}",
    },
    PLATFORM_EMBY: {
        "movie_folder_template": "{title} ({year})",
        "movie_file_template": "{title} ({year})",
        "series_folder_template": "{series} ({year_range})",
        "season_folder_template": "Season {season:02d}",
        "episode_file_template": "{series} S{season:02d}E{episode:02d} - {episode_title}",
    },
    PLATFORM_GENERIC: {
        "movie_folder_template": "{title} [{year}]",
        "movie_file_template": "{title} [{year}]",
        "series_folder_template": "{series} [{year_range}]",
        "season_folder_template": "Season {season:02d}",
        "episode_file_template": "{series} S{season:02d}E{episode:02d} - {episode_title}",
    },
}

# Default configuration
DEFAULT_CONFIG = {
    # App settings
    "app_version": "2.0.0",

    # LLM Provider settings
    "llm_provider": "openai",  # openai, anthropic, google, openrouter

    # API Keys for different providers
    "openai_api_key": "",
    "anthropic_api_key": "",
    "google_api_key": "",
    "openrouter_api_key": "",

    # Model selection
    "openai_model": "gpt-4o",
    "anthropic_model": "claude-sonnet-4-20250514",
    "google_model": "gemini-2.0-flash",
    "openrouter_model": "openai/gpt-4o-mini",

    "use_web_search": True,

    # Platform settings
    "platform": PLATFORM_GENERIC,  # plex, jellyfin, emby, generic
    "plex_agent": "",  # Empty = auto/disabled (optional)
    "plex_scanner": "",  # Empty = auto/disabled (optional)
    "plex_options_enabled": False,  # Whether Plex-specific options are used

    # Mode settings
    "mode": "media",  # media (Plex/Jellyfin optimized) or mass (generic file renaming)

    # Custom prompt override (if set, overrides built-in prompts)
    "custom_prompt": "",
    "custom_prompt_enabled": False,

    # Naming templates (loaded from platform preset by default)
    "movie_folder_template": "{title} [{year}]",
    "movie_file_template": "{title} [{year}]",
    "series_folder_template": "{series} [{year_range}]",
    "season_folder_template": "Season {season:02d}",
    "episode_file_template": "{series} S{season:02d}E{episode:02d} - {episode_title}",

    # Mass rename settings (for generic file renaming)
    "mass_rename_pattern": "{name}_{counter:03d}",
    "mass_rename_extensions": ["*"],  # All files, or specific extensions
    "mass_rename_use_ai": True,  # Use AI to suggest better names

    # Supported video extensions (for media mode)
    "video_extensions": [
        # Common video formats
        ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".m2ts", ".vob",
        ".divx", ".xvid", ".asf", ".rm", ".rmvb", ".ogv",
        # Additional video formats
        ".mts", ".m2v", ".mp2", ".mpe", ".mpv", ".m1v",
        ".f4v", ".f4p", ".f4a", ".f4b",  # Flash video
        ".3g2", ".3gpp", ".3gpp2",  # Mobile video
        ".hevc", ".h264", ".h265", ".avc",  # Codec-named
        ".qt", ".yuv", ".amv", ".mxf", ".roq", ".nsv",
        ".bik", ".smk",  # Game video formats
        ".drc", ".gifv", ".mng", ".svi",
        ".wtv", ".dvr-ms",  # Windows recorded TV
        ".iso",  # DVD/Blu-ray ISOs (optional, can contain video)
    ],

    # Supported audio extensions (for music/audio mode)
    "audio_extensions": [
        ".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus",
        ".wma", ".alac", ".aiff", ".ape", ".dsd", ".dsf", ".dff",
        ".mpc", ".tak", ".tta", ".wv", ".ac3", ".dts",
        # Additional audio formats
        ".mid", ".midi", ".kar",  # MIDI
        ".ra", ".ram",  # RealAudio
        ".au", ".snd",  # Unix audio
        ".voc", ".8svx",  # Legacy formats
        ".cda",  # CD audio track
        ".mka",  # Matroska audio
        ".spx",  # Speex
        ".gsm", ".amr", ".awb",  # Mobile audio
        ".w64", ".rf64",  # Broadcast Wave
        ".caf",  # Apple Core Audio
        ".m4b", ".m4p",  # iTunes formats
    ],

    # Subtitle extensions (to rename alongside video files)
    "subtitle_extensions": [
        ".srt", ".sub", ".ass", ".ssa", ".vtt", ".idx",
        ".smi", ".usf", ".pjs", ".mpl", ".dks",
        ".stl", ".sbv", ".dfxp", ".ttml",  # Additional formats
    ],

    # Common document extensions (for mass mode suggestions)
    "document_extensions": [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".rtf", ".txt", ".md", ".csv",
        ".epub", ".mobi", ".azw", ".azw3",  # E-books
        ".pages", ".numbers", ".key",  # Apple iWork
        ".tex", ".latex",  # LaTeX
    ],

    # Common image extensions (for mass mode)
    "image_extensions": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
        ".tiff", ".tif", ".ico", ".heic", ".heif",
        ".raw", ".cr2", ".nef", ".arw", ".dng",  # RAW formats
        ".psd", ".ai", ".eps",  # Adobe
        ".xcf",  # GIMP
    ],

    # Common archive extensions (for mass mode)
    "archive_extensions": [
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".cab", ".iso", ".dmg",
    ],

    # Metadata settings
    "show_metadata": True,  # Show metadata info in scan results
    "suggest_metadata_updates": True,  # Suggest metadata updates based on AI analysis
    "auto_update_metadata": False,  # Automatically update metadata (requires user approval)

    # Confidence threshold (0-100) - below this, files are flagged for manual review
    "confidence_threshold": 80,

    # Excluded paths (absolute paths or patterns)
    "excluded_paths": [],

    # Excluded folder names (will skip any folder with these names)
    "excluded_folder_names": [
        "Personal", "Private", "My Documents", "Documents",
        "Windows", "Program Files", "Program Files (x86)", "ProgramData",
        "AppData", "$Recycle.Bin", "System Volume Information",
        "Photos", "Pictures", "Images", "Music", "Audio",
        "Games", "Software", "Apps", "Applications", "Programs", "Installers",
        "Backup", "Backups", "Old", "Archive", "Archives", "Temp", "tmp",
        "node_modules", ".git", ".svn", "__pycache__", "venv", ".venv",
        "Work", "Projects", "Development", "Code", "Source",
        "Study", "StudyWithMe", "Tutorials", "Tutorial", "Courses", "Course",
        "Learning", "Lessons", "Education", "Training", "Books", "Ebooks",
        "Downloads", "Desktop", "Fonts", "Drivers", "ISO", "ISOs"
    ],

    # Folder name patterns that suggest media content
    "media_folder_hints": [
        "movie", "movies", "film", "films", "cinema",
        "series", "tv", "show", "shows", "episode", "episodes", "season",
        "video", "videos", "media", "entertainment",
        "720p", "1080p", "2160p", "4k", "hdr", "bluray", "blu-ray",
        "webrip", "web-dl", "hdtv", "dvdrip", "brrip", "x264", "x265", "hevc"
    ],

    # Enable smart folder pre-filtering with GPT
    "smart_folder_filter": True,

    # Enable folder restructuring
    "restructure_folders": True,

    # Enable folder renaming (clean scene-release names, normalize season folders)
    "rename_folders": True,

    # Rename subtitles alongside video files
    "rename_subtitles": True,

    # Batch size for GPT API calls (smaller = more reliable with web search)
    "gpt_batch_size": 12,

    # Number of parallel GPT workers
    "gpt_parallel_workers": 3,

    # Recently used paths for quick access
    "recent_paths": [],

    # Default target path
    "default_target_path": "",

    # UI preferences
    "ui_theme": "default",
    "show_advanced_options": False,

    # Session state (auto-saved on close, restored on open)
    "last_path": "",
    "window_geometry": "",
}


def load_config() -> dict:
    """
    Load configuration from file or create default.
    Config is stored in Windows Documents/Renameify folder.
    """
    config_file = get_config_file()

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # Merge with defaults (user config takes priority)
                config = {**DEFAULT_CONFIG, **user_config}
                return config
        except (json.JSONDecodeError, IOError):
            pass

    # Return defaults and save them
    save_config(DEFAULT_CONFIG.copy())
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_file = get_config_file()
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_api_key(provider: str = None) -> str:
    """Get API key for the specified provider (or current provider) from config or environment."""
    config = load_config()
    if provider is None:
        provider = config.get("llm_provider", "openai")

    key_map = {
        "openai": ("openai_api_key", "OPENAI_API_KEY"),
        "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
        "google": ("google_api_key", "GOOGLE_API_KEY"),
        "openrouter": ("openrouter_api_key", "OPENROUTER_API_KEY"),
    }

    config_key, env_key = key_map.get(provider, ("openai_api_key", "OPENAI_API_KEY"))
    api_key = config.get(config_key) or os.environ.get(env_key, "")
    return api_key


def set_api_key(api_key: str, provider: str = None) -> None:
    """Set API key for the specified provider (or current provider) in config."""
    config = load_config()
    if provider is None:
        provider = config.get("llm_provider", "openai")

    key_map = {
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "google": "google_api_key",
        "openrouter": "openrouter_api_key",
    }

    config_key = key_map.get(provider, "openai_api_key")
    config[config_key] = api_key
    save_config(config)


def get_current_model() -> str:
    """Get the current model based on the selected provider."""
    config = load_config()
    provider = config.get("llm_provider", "openai")
    model_key = f"{provider}_model"
    return config.get(model_key, "gpt-4o-mini")


def set_current_model(model: str, provider: str = None) -> None:
    """Set the model for the specified provider."""
    config = load_config()
    if provider is None:
        provider = config.get("llm_provider", "openai")
    model_key = f"{provider}_model"
    config[model_key] = model
    save_config(config)


# Available models for each provider (updated for latest 2025-2026 models)
# This is the default/fallback list - can be updated dynamically via fetch_available_models()
AVAILABLE_MODELS = {
    "openai": [
        ("gpt-4o-mini", "GPT-4o Mini - Fast & affordable"),
        ("gpt-4o", "GPT-4o - Most capable multimodal"),
        ("gpt-4-turbo", "GPT-4 Turbo - High performance"),
        ("gpt-4.1", "GPT-4.1 - Latest GPT-4"),
        ("gpt-4.1-mini", "GPT-4.1 Mini - Fast GPT-4.1"),
        ("gpt-4.1-nano", "GPT-4.1 Nano - Ultra-fast"),
        ("gpt-5", "GPT-5 - Next generation"),
        ("gpt-5-mini", "GPT-5 Mini - Balance of speed & capability"),
        ("o3", "o3 - Advanced reasoning"),
        ("o3-mini", "o3-mini - Fast reasoning"),
        ("o4-mini", "o4-mini - Latest reasoning model"),
    ],
    "anthropic": [
        ("claude-sonnet-4-20250514", "Claude Sonnet 4 - Balanced"),
        ("claude-opus-4-20250514", "Claude Opus 4 - Most capable"),
        ("claude-haiku-4-20250514", "Claude Haiku 4 - Fast & efficient"),
        ("claude-4.5-sonnet", "Claude 4.5 Sonnet - Latest balanced"),
        ("claude-4.5-opus", "Claude 4.5 Opus - Latest flagship"),
    ],
    "google": [
        ("gemini-2.0-flash", "Gemini 2.0 Flash - Fast"),
        ("gemini-2.0-pro", "Gemini 2.0 Pro - Advanced"),
        ("gemini-2.5-pro", "Gemini 2.5 Pro - Latest flagship"),
        ("gemini-2.5-flash", "Gemini 2.5 Flash - Latest fast"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro - Balanced"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash - Efficient"),
    ],
    "openrouter": [
        ("openai/gpt-4o-mini", "OpenAI GPT-4o Mini"),
        ("openai/gpt-4o", "OpenAI GPT-4o"),
        ("openai/gpt-5", "OpenAI GPT-5"),
        ("openai/o3-mini", "OpenAI o3-mini"),
        ("anthropic/claude-sonnet-4", "Anthropic Claude Sonnet 4"),
        ("anthropic/claude-opus-4", "Anthropic Claude Opus 4"),
        ("google/gemini-2.0-flash", "Google Gemini 2.0 Flash"),
        ("google/gemini-2.5-pro", "Google Gemini 2.5 Pro"),
        ("meta-llama/llama-3.3-70b-instruct", "Meta Llama 3.3 70B"),
        ("meta-llama/llama-4-maverick", "Meta Llama 4 Maverick"),
        ("mistralai/mistral-large", "Mistral Large"),
        ("mistralai/mistral-medium-3", "Mistral Medium 3"),
        ("deepseek/deepseek-chat", "DeepSeek Chat"),
        ("deepseek/deepseek-r1", "DeepSeek R1 - Reasoning"),
    ],
}

# Cache for dynamically fetched models
_cached_models = {}
_cache_timestamp = 0
MODEL_CACHE_DURATION = 3600  # 1 hour in seconds


def get_available_models(provider: str = None) -> list:
    """Get list of available models for a provider."""
    if provider is None:
        config = load_config()
        provider = config.get("llm_provider", "openai")
    return AVAILABLE_MODELS.get(provider, AVAILABLE_MODELS["openai"])


def get_platform_templates(platform: str) -> dict:
    """Get naming templates for a specific platform."""
    return PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES[PLATFORM_GENERIC])


def set_platform(platform: str) -> None:
    """Set the current platform and update templates."""
    config = load_config()
    config["platform"] = platform

    # Update templates based on platform
    templates = get_platform_templates(platform)
    config.update(templates)

    save_config(config)


def get_custom_prompt() -> Optional[str]:
    """Get the custom prompt if enabled."""
    config = load_config()
    if config.get("custom_prompt_enabled") and config.get("custom_prompt"):
        return config["custom_prompt"]
    return None


def set_custom_prompt(prompt: str, enabled: bool = True) -> None:
    """Set a custom prompt override."""
    config = load_config()
    config["custom_prompt"] = prompt
    config["custom_prompt_enabled"] = enabled
    save_config(config)


def add_exclusion(path: str) -> None:
    """Add a path to exclusions."""
    config = load_config()
    if path not in config["excluded_paths"]:
        config["excluded_paths"].append(path)
        save_config(config)


def remove_exclusion(path: str) -> None:
    """Remove a path from exclusions."""
    config = load_config()
    if path in config["excluded_paths"]:
        config["excluded_paths"].remove(path)
        save_config(config)


def list_exclusions() -> list:
    """List all exclusions."""
    config = load_config()
    return config.get("excluded_paths", []) + config.get("excluded_folder_names", [])


def add_recent_path(path: str) -> None:
    """Add a path to recent paths."""
    config = load_config()
    recent = config.get("recent_paths", [])

    # Remove if already exists
    if path in recent:
        recent.remove(path)

    # Add to front
    recent.insert(0, path)

    # Keep only last 10
    config["recent_paths"] = recent[:10]
    save_config(config)


def get_recent_paths() -> list:
    """Get recent paths."""
    config = load_config()
    return config.get("recent_paths", [])


def fetch_available_models(provider: str = None, api_key: str = None) -> list:
    """
    Fetch available models from the provider's API.
    Returns list of tuples: (model_id, description)
    Falls back to cached/default list on error.
    """
    import time
    global _cached_models, _cache_timestamp

    if provider is None:
        config = load_config()
        provider = config.get("llm_provider", "openai")

    # Check cache
    cache_key = provider
    current_time = time.time()
    if cache_key in _cached_models and (current_time - _cache_timestamp) < MODEL_CACHE_DURATION:
        return _cached_models[cache_key]

    if api_key is None:
        api_key = get_api_key(provider)

    if not api_key:
        return AVAILABLE_MODELS.get(provider, [])

    try:
        models = _fetch_models_from_api(provider, api_key)
        if models:
            _cached_models[cache_key] = models
            _cache_timestamp = current_time
            return models
    except Exception:
        pass

    return AVAILABLE_MODELS.get(provider, [])


def _fetch_models_from_api(provider: str, api_key: str) -> list:
    """Internal function to fetch models from API.

    For OpenAI, only models that support the web_search_preview tool (Responses API)
    are returned.  For other providers, all chat-capable models are returned.
    """
    import httpx

    models = []

    if provider == "openai":
        try:
            response = httpx.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                capable = []
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    if is_web_search_capable(model_id):
                        capable.append(model_id)

                # Sort: newer (longer/dated) models first, then deduplicate
                capable = sorted(set(capable), reverse=True)

                for model_id in capable[:20]:
                    desc = _get_model_description(model_id)
                    models.append((model_id, desc))
        except Exception:
            pass

    elif provider == "openrouter":
        try:
            response = httpx.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                for m in data.get("data", [])[:40]:
                    model_id = m.get("id", "")
                    name = m.get("name", model_id)
                    if not name or name == model_id:
                        name = _get_model_description(model_id)
                    models.append((model_id, name))
        except Exception:
            pass

    return models


def _get_model_description(model_id: str) -> str:
    """Generate a human-readable description for a model ID."""
    descriptions = {
        "gpt-5": "GPT-5 - Next generation flagship",
        "gpt-5-mini": "GPT-5 Mini - Fast next-gen",
        "gpt-4o": "GPT-4o - Multimodal flagship",
        "gpt-4o-mini": "GPT-4o Mini - Fast & affordable",
        "gpt-4-turbo": "GPT-4 Turbo - High performance",
        "gpt-4.1": "GPT-4.1 - Latest GPT-4",
        "gpt-4.1-mini": "GPT-4.1 Mini - Fast",
        "o3": "o3 - Advanced reasoning",
        "o3-mini": "o3-mini - Fast reasoning",
        "o4-mini": "o4-mini - Latest reasoning",
    }

    for key, desc in descriptions.items():
        if key in model_id:
            return desc

    return model_id.replace("-", " ").title()


def clear_model_cache():
    """Clear the cached models to force a refresh."""
    global _cached_models, _cache_timestamp
    _cached_models = {}
    _cache_timestamp = 0


# Model IDs / prefixes that support OpenAI's web_search_preview tool
# (Responses API).  Reasoning models (o1/o3/o4) and older GPT-3.5 do not.
_WEB_SEARCH_CAPABLE_PREFIXES = (
    "gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-5",
)
_WEB_SEARCH_EXCLUDED_KEYWORDS = ("instruct", "vision", "embedding", "whisper", "tts")


def is_web_search_capable(model_id: str) -> bool:
    """Return True if the OpenAI *model_id* is expected to support web_search_preview."""
    mid = model_id.lower()
    # Exclude known non-chat / non-tool models
    for kw in _WEB_SEARCH_EXCLUDED_KEYWORDS:
        if kw in mid:
            return False
    # Exclude reasoning-only models (o1, o3, o4 series)
    if re.match(r'^o\d', mid):
        return False
    # Accept known capable prefixes
    for prefix in _WEB_SEARCH_CAPABLE_PREFIXES:
        if mid.startswith(prefix):
            return True
    return False

