# Renameify – AI Agent Guidelines

## Architecture Overview

Windows-only Tkinter desktop app that scans media folders, sends filenames to an LLM for identification, and renames/reorganizes files to match Plex/Jellyfin/Emby naming conventions.

**Core data flow:**
```
Scanner → MediaFile[]  →  gpt_service.identify_all_media → MediaInfo[]
       → renamer.generate_rename_plan → RenamePlan (+ RenameManifest)
       → renamer.execute_rename_plan → files renamed on disk
       → rollback.execute_rollback   → undo via saved manifest
```

**Module map:**
| Path | Responsibility |
|------|----------------|
| `Renameify.py` | Entry point; adds `src/` to `sys.path` in dev mode |
| `src/core/config.py` | Config load/save, `PLATFORM_TEMPLATES`, `DEFAULT_CONFIG` |
| `src/core/gpt_service.py` | All LLM calls, `MediaInfo` dataclass, batching, cancellation |
| `src/core/metadata.py` | Read/write file metadata (mutagen-based for audio/video tags) |
| `src/core/renamer.py` | `generate_rename_plan`, `execute_rename_plan`, folder cleanup patterns |
| `src/core/scanner.py` | Recursive media scanner → `MediaFile` / `SubtitleFile` |
| `src/core/rollback.py` | `RenameManifest` persistence for undo |
| `src/prompts/` | Built-in and custom LLM prompt management |
| `src/platforms/base.py` | `Platform` ABC, `NamingTemplate` dataclass |
| `src/platforms/{plex,jellyfin,emby,generic}.py` | Platform-specific implementations |
| `src/gui/app.py` | Tkinter GUI (runs all heavy work on background threads) |
| `src/utils/folder_filter.py` | Smart GPT-based folder classification (media vs. non-media) |
| `src/utils/folder_fixer.py` | Auto-fix merged/malformed folder structures (`FolderFix` operations) |
| `src/utils/drive_utils.py` | Windows drive enumeration (local + network paths) |

## Developer Workflows

**Run in dev mode:**
```powershell
pip install -r requirements.txt
python Renameify.py
```

**Build portable EXE (non-interactive):**
```bat
build.bat portable     # → dist\portable\Renameify.exe
build.bat release      # clean + bootstrap + both + verify
build.bat bootstrap    # create/repair .venv only
```
`build.bat` creates `.venv` automatically and delegates to `build\build.py` (PyInstaller). The build uses `--paths=src` so all `src/` subpackages are bundled without path hacks.

**Config location (runtime):** `%USERPROFILE%\Documents\Renameify\renameify_config.json`  
**Logs / rollback manifests:** `%USERPROFILE%\Documents\Renameify\logs\`

## Import Convention

All internal imports use **absolute** style (not relative) because `sys.path.insert(0, src_dir)` is applied at startup in dev mode and PyInstaller collects with `--paths=src`:

```python
# ✅ Correct (used everywhere)
from core.config import load_config
from prompts import get_prompt_manager

# ❌ Wrong – relative imports break in entry-point context
from .config import load_config
```

`gpt_service.py` uses a try/except fallback for the prompts import to handle both modes.

## LLM Integration Patterns

**Multi-provider `call_llm()`** in `gpt_service.py` dispatches to `_call_openai`, `_call_anthropic`, `_call_google`, or `_call_openrouter` based on `config["llm_provider"]`.

**OpenAI web search** uses the Responses API with `web_search_preview` tool, falling back to Chat Completions if that fails:
```python
client.responses.create(model=model, tools=[{"type": "web_search_preview"}], ...)
```

**Batching:** Files are grouped by parent folder first (same-folder files stay together), then chunked to `config["gpt_batch_size"]` (default 12). Parallel workers: 2 when web search is on, up to 3 otherwise.

**JSON recovery (`_extract_json_array`):** Handles markdown fences, truncated responses, and stray text. Never assume clean JSON from the LLM — always call this helper.

## Cancellation System

```python
token = reset_cancel()           # start fresh; increment generation counter
bind_cancel_token(token)         # call inside each worker thread
is_cancelled()                   # check in tight loops
request_cancel()                 # signal from GUI
_sleep_with_cancel(seconds)      # interruptible sleep
```

Raising `InterruptedError("Operation cancelled")` propagates up cleanly; callers catch it and return partial results.

## Season Extraction & Naming Rules

`extract_season_from_path()` in `gpt_service.py` walks parent folders and recognises **10+ language patterns** (Season, Series, Staffel, Temporada, Saison, S01, etc.). Its result **always overrides** the LLM-returned season field. Specials folders (`specials`, `bts`, `featurettes`, etc.) map to season 0.

`normalize_season_folder_name()` in `renamer.py` normalises any variant to `Season 01` format.

## Rename Plan Categorisation

`generate_rename_plan()` sorts items into:
- **`high_confidence`** – `confidence >= config["confidence_threshold"]` (default 80)
- **`low_confidence`** – below threshold, shown to user for review
- **`unknown`** – skipped silently
- **`skipped`** – already matches `PROPER_NAME_PATTERNS` or inside BDMV structure

`folder_renames` are executed **before** file operations; paths in the plan are updated to reflect the new folder names.

## Platform Templates

Templates live in `PLATFORM_TEMPLATES` dict in `config.py`. Calling `set_platform(platform)` writes the chosen platform's templates into the config. Example Plex episode template:
```
{series} - S{season:02d}E{episode:02d} - {episode_title}
```
Generic uses `[year]` brackets; Plex/Jellyfin/Emby use `(year)` parentheses.

## Key Files for Common Tasks

- **Add a new LLM provider** → `gpt_service.py` (`call_llm`, add `_call_<provider>`) + `config.py` (`AVAILABLE_MODELS`, `DEFAULT_CONFIG`)
- **Change naming templates** → `config.py` `PLATFORM_TEMPLATES`
- **Modify LLM prompts** → `src/prompts/builtin.py`
- **Add file type support** → `config.py` `video_extensions` / `audio_extensions`
- **Build system** → `build.bat` + `build/build.py`

## Optional Features

**Metadata Support (`src/core/metadata.py`):**
Uses `mutagen` to read/write audio/video tags (ID3, MP4, FLAC, Vorbis, AIFF, WAVE). Optional — gracefully falls back if mutagen not installed. Check `is_mutagen_available()` before offering metadata features in GUI.

**Smart Folder Filtering (`src/utils/folder_filter.py`):**
Pre-classifies folders (media/personal/system/other) with GPT before deep scanning. Saves time on large drives. Used in GUI's scan initialization to skip non-media folders.

**Folder Fixing (`src/utils/folder_fixer.py`):**
Auto-detects and fixes malformed folder structures (e.g., `"Show [2020]Season 01"` → `"Show [2020]/Season 01/"`). Called during rename planning.
