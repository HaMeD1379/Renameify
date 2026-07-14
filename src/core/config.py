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

# Plex Agent/Scanner options. Values are stable app option keys; ids/names mirror
# the current Plex library choices and include legacy values where Plex still
# exposes them for migrated libraries.
PLEX_AGENT_OPTIONS = {
    "auto": {
        "id": "",
        "name": "Auto",
        "library_type": "auto",
        "description": "Use normal Renameify detection without forcing a Plex library type.",
    },
    "plex_movie": {
        "id": "tv.plex.agents.movie",
        "name": "Plex Movie",
        "library_type": "movie",
        "description": "Current default movie metadata agent.",
    },
    "plex_series": {
        "id": "tv.plex.agents.series",
        "name": "Plex Series",
        "library_type": "series",
        "description": "Current default TV metadata agent.",
    },
    "personal_media": {
        "id": "com.plexapp.agents.none",
        "name": "Personal Media",
        "library_type": "other",
        "description": "For videos that should not match online databases.",
    },
    "legacy_thetvdb": {
        "id": "com.plexapp.agents.thetvdb",
        "name": "TheTVDB (Legacy)",
        "library_type": "series",
        "description": "Legacy TV agent retained for older libraries.",
    },
    "legacy_tmdb": {
        "id": "com.plexapp.agents.themoviedb",
        "name": "The Movie Database (Legacy)",
        "library_type": "movie",
        "description": "Legacy movie agent; Plex recommends Plex Movie instead.",
    },
}

PLEX_SCANNER_OPTIONS = {
    "auto": {
        "id": "",
        "name": "Auto",
        "library_type": "auto",
        "description": "Let Renameify classify movies and shows from folder context.",
    },
    "plex_movie": {
        "id": "Plex Movie",
        "name": "Plex Movie",
        "library_type": "movie",
        "description": "Current default movie scanner paired with Plex Movie.",
    },
    "plex_tv_series": {
        "id": "Plex TV Series",
        "name": "Plex TV Series",
        "library_type": "series",
        "description": "Current default TV scanner paired with Plex Series.",
    },
    "plex_video_files": {
        "id": "Plex Video Files",
        "name": "Plex Video Files",
        "library_type": "other",
        "description": "Less strict personal-video scanner; no online matching.",
    },
    "legacy_movie": {
        "id": "Plex Movie Scanner",
        "name": "Plex Movie Scanner (Legacy)",
        "library_type": "movie",
        "description": "Deprecated movie scanner for older libraries.",
    },
    "legacy_series": {
        "id": "Plex Series Scanner",
        "name": "Plex Series Scanner (Legacy)",
        "library_type": "series",
        "description": "Deprecated TV scanner for older libraries.",
    },
}

PLEX_EPISODE_ORDERING_OPTIONS = {
    "tmdb_aired": "The Movie Database (Aired)",
    "tvdb_aired": "TheTVDB (Aired)",
    "tvdb_dvd": "TheTVDB (DVD)",
    "tvdb_absolute": "TheTVDB (Absolute)",
}

# Backwards-compatible constants used by older code/configs.
PLEX_AGENT_PLEX_MOVIE = PLEX_AGENT_OPTIONS["plex_movie"]["id"]
PLEX_AGENT_PLEX_SERIES = PLEX_AGENT_OPTIONS["plex_series"]["id"]
PLEX_AGENT_TMDB = PLEX_AGENT_OPTIONS["legacy_tmdb"]["id"]
PLEX_SCANNER_PLEX_MOVIE = PLEX_SCANNER_OPTIONS["plex_movie"]["id"]
PLEX_SCANNER_PLEX_SERIES = PLEX_SCANNER_OPTIONS["plex_tv_series"]["id"]


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
    "openai_model": "gpt-4o-mini",
    "anthropic_model": "claude-sonnet-4-20250514",
    "google_model": "gemini-2.0-flash",
    "openrouter_model": "openai/gpt-4o-mini",

    "use_web_search": True,

    # Platform settings
    "platform": PLATFORM_GENERIC,  # plex, jellyfin, emby, generic
    "plex_agent": "auto",
    "plex_scanner": "auto",
    "plex_episode_ordering": "tmdb_aired",
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
    "ui_theme": "dark",
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
                normalize_plex_options(config)
                return config
        except (json.JSONDecodeError, IOError):
            pass

    # Return defaults and save them
    config = DEFAULT_CONFIG.copy()
    normalize_plex_options(config)
    save_config(config)
    return config


def save_config(config: dict) -> None:
    """Save configuration to file."""
    normalize_plex_options(config)
    config_file = get_config_file()
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def normalize_plex_options(config: dict) -> dict:
    """Normalize legacy/free-text Plex agent and scanner settings in-place."""
    agent_aliases = {
        "": "auto",
        "auto": "auto",
        "plex movie": "plex_movie",
        "tv.plex.agents.movie": "plex_movie",
        "plex series": "plex_series",
        "plex tv series": "plex_series",
        "tv.plex.agents.series": "plex_series",
        "personal media": "personal_media",
        "personal media shows": "personal_media",
        "com.plexapp.agents.none": "personal_media",
        "thetvdb": "legacy_thetvdb",
        "thetvdb (legacy)": "legacy_thetvdb",
        "com.plexapp.agents.thetvdb": "legacy_thetvdb",
        "the movie database": "legacy_tmdb",
        "the movie database (legacy)": "legacy_tmdb",
        "com.plexapp.agents.themoviedb": "legacy_tmdb",
        "com.plexapp.agents.imdb": "legacy_tmdb",
    }
    scanner_aliases = {
        "": "auto",
        "auto": "auto",
        "plex movie": "plex_movie",
        "plex movie scanner": "legacy_movie",
        "plex movie scanner (legacy)": "legacy_movie",
        "plex tv series": "plex_tv_series",
        "plex series": "plex_tv_series",
        "plex series scanner": "legacy_series",
        "plex series scanner (legacy)": "legacy_series",
        "plex video files": "plex_video_files",
        "plex video files scanner": "plex_video_files",
    }

    agent = str(config.get("plex_agent", "auto")).strip()
    scanner = str(config.get("plex_scanner", "auto")).strip()
    ordering = str(config.get("plex_episode_ordering", "tmdb_aired")).strip()

    config["plex_agent"] = agent if agent in PLEX_AGENT_OPTIONS else agent_aliases.get(agent.lower(), "auto")
    config["plex_scanner"] = scanner if scanner in PLEX_SCANNER_OPTIONS else scanner_aliases.get(scanner.lower(), "auto")
    if ordering not in PLEX_EPISODE_ORDERING_OPTIONS:
        config["plex_episode_ordering"] = "tmdb_aired"
    return config


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


OPENAI_WEB_SEARCH_MODEL_LIMIT = 5

# Curated for Renameify's workload: short JSON identification calls that benefit
# from OpenAI Responses web search. Keep this list small so the UI is a decision,
# not a raw model catalog.
OPENAI_WEB_SEARCH_MODELS = [
    {
        "id": "gpt-4o-mini",
        "name": "Recommended value",
        "description": "Recommended value - fast, reliable, low cost",
        "detail": "Best default for media lookup",
        "cost_tier": "$",
        "badge": "Recommended",
    },
    {
        "id": "gpt-4.1-nano",
        "name": "Lowest cost",
        "description": "Lowest cost - smallest web-capable GPT",
        "detail": "Use for large cheap batches",
        "cost_tier": "$",
        "badge": "Budget",
    },
    {
        "id": "gpt-4.1-mini",
        "name": "Balanced",
        "description": "Balanced - better matching, still affordable",
        "detail": "Use when messy releases need more context",
        "cost_tier": "$$",
        "badge": "Balanced",
    },
    {
        "id": "gpt-4o",
        "name": "Proven quality",
        "description": "Proven quality - strong media reasoning",
        "detail": "Use when accuracy matters more than cost",
        "cost_tier": "$$$",
        "badge": "Quality",
    },
    {
        "id": "gpt-4.1",
        "name": "Max accuracy",
        "description": "Max accuracy - highest-cost fallback",
        "detail": "Use for hard folders after review",
        "cost_tier": "$$$$",
        "badge": "Premium",
    },
]


def _public_model_option(option: dict) -> dict:
    item = dict(option)
    item["supports_web_search"] = True
    return item


def _model_available(model_id: str, available_ids: Optional[set]) -> bool:
    if not available_ids:
        return True
    return model_id in available_ids or any(item.startswith(f"{model_id}-") for item in available_ids)


def get_openai_web_search_models(available_ids=None) -> list:
    """Return exactly five ranked OpenAI web-search-capable model options."""
    available = set(available_ids or [])
    selected = []
    selected_ids = set()

    for option in OPENAI_WEB_SEARCH_MODELS:
        if _model_available(option["id"], available):
            selected.append(option)
            selected_ids.add(option["id"])

    # Preserve the five-option UX even if the model endpoint omits aliases.
    for option in OPENAI_WEB_SEARCH_MODELS:
        if len(selected) >= OPENAI_WEB_SEARCH_MODEL_LIMIT:
            break
        if option["id"] not in selected_ids:
            selected.append(option)
            selected_ids.add(option["id"])

    return [_public_model_option(option) for option in selected[:OPENAI_WEB_SEARCH_MODEL_LIMIT]]


# Available models for each provider. OpenAI is intentionally limited to the
# five recommended web-search-capable options used by Test & Refresh.
AVAILABLE_MODELS = {
    "openai": get_openai_web_search_models(),
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
    models = AVAILABLE_MODELS.get(provider, AVAILABLE_MODELS["openai"])
    if provider == "openai":
        return get_openai_web_search_models()
    return models[:OPENAI_WEB_SEARCH_MODEL_LIMIT]


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
    import hashlib
    import time
    global _cached_models, _cache_timestamp

    if provider is None:
        config = load_config()
        provider = config.get("llm_provider", "openai")

    if api_key is None:
        api_key = get_api_key(provider)

    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:10] if api_key else "none"
    cache_key = f"{provider}:{fingerprint}"
    current_time = time.time()
    if cache_key in _cached_models and (current_time - _cache_timestamp) < MODEL_CACHE_DURATION:
        return _cached_models[cache_key]

    if not api_key:
        return get_available_models(provider)

    try:
        models = _fetch_models_from_api(provider, api_key)
        if models:
            _cached_models[cache_key] = models
            _cache_timestamp = current_time
            return models
    except Exception:
        pass

    return get_available_models(provider)


def _fetch_models_from_api(provider: str, api_key: str) -> list:
    """Internal function to fetch models from API.

    For OpenAI, only the five recommended Responses web-search models are
    returned. Other providers are limited to their fallback top five because
    Renameify does not implement provider-native web tools for them yet.
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
                models = get_openai_web_search_models(set(capable))
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
                for m in data.get("data", [])[:OPENAI_WEB_SEARCH_MODEL_LIMIT]:
                    model_id = m.get("id", "")
                    name = m.get("name", model_id)
                    if not name or name == model_id:
                        name = _get_model_description(model_id)
                    models.append((model_id, name))
        except Exception:
            pass

    return models[:OPENAI_WEB_SEARCH_MODEL_LIMIT]


def _get_model_description(model_id: str) -> str:
    """Generate a human-readable description for a model ID."""
    descriptions = {
        "gpt-4o-mini": "GPT-4o Mini - Fast & affordable",
        "gpt-4o": "GPT-4o - Multimodal flagship",
        "gpt-4.1-nano": "GPT-4.1 Nano - Lowest cost",
        "gpt-4.1-mini": "GPT-4.1 Mini - Fast",
        "gpt-4.1": "GPT-4.1 - High accuracy",
        "gpt-4-turbo": "GPT-4 Turbo - High performance",
    }

    for key in sorted(descriptions, key=len, reverse=True):
        if key in model_id:
            desc = descriptions[key]
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

