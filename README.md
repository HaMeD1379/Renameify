# 🎬 Renameify v2.2.0

<div align="center">

**AI-Powered Media File Renaming for Your Media Server**

Transform chaotic media libraries into perfectly organized collections with GPT-4o, Claude, or Gemini.

[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=flat-square)](https://www.python.org)
[![Flutter](https://img.shields.io/badge/Flutter-3.0%2B-blue.svg?style=flat-square)](https://flutter.dev)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue.svg?style=flat-square)]()

**Perfect for:**
- 🎭 [**Plex**](https://www.plex.tv/) Media Server
- 📺 [**Jellyfin**](https://jellyfin.org/) Open-Source Media System  
- 🎬 [**Emby**](https://emby.media/) Media Server
- 📂 Generic folder structures

**Powered by:** GPT-4o • Claude Sonnet 4 • Gemini 2.0 • OpenRouter

</div>

---

## ✨ What Makes Renameify Different?

Renameify goes beyond simple regex patterns. Using advanced AI models with **live web search**, it:

✅ **Identifies messy media files** — Parse garbled names like `Breaking.Bad.S01E01.720p.BluRay.x265-RARBG.mkv`  
✅ **Finds real episode titles** — Searches TMDB/TheTVDB for "Pilot", "Cat's in the Bag...", etc.  
✅ **Respects folder structure** — Extracts season from folder (`Season 02/01.mkv` → S02E01)  
✅ **Organizes by platform** — Generates names perfect for Plex, Jellyfin, or Emby  
✅ **Handles 100+ files** — Fast batch processing with parallel API calls  
✅ **Full rollback support** — Undo any operation with saved manifests  
✅ **Works on network paths** — UNC shares like `\\nas\media\tv`  

---

## 🚀 Quick Start

### Step 1: Install
- Download the latest `Renameify-<version>-Setup.exe` from releases.
- Run the installer and launch Renameify from the Start menu or desktop shortcut.

### Step 2: Add API Key
1. Launch `Renameify.exe`
2. Go to **Settings** → **LLM Provider**
3. Choose your provider:
   - **OpenAI** (Recommended) — [Get API key](https://platform.openai.com/account/api-keys)
   - **Anthropic** — [Get API key](https://console.anthropic.com/)
   - **Google Gemini** — [Get API key](https://makersuite.google.com/app/apikey)
4. Paste your API key and test connection

### Step 3: Configure Platform
1. Go to **Settings** → **Naming Mode**
2. Select your media server:
   - **Generic** (default — works with any naming)
   - **Plex** (configure Agent/Scanner)
   - **Jellyfin**
   - **Emby**

### Step 4: Scan & Rename
1. Click **Browse** and select your media folder
2. Click **Discover Files** or **Identify & Plan**
3. Review and edit the proposed renames
4. Click **Apply Selected** to apply changes
5. Done! Your files are renamed and organized

---

## 💻 Advanced Usage (Development)

For developers and power users:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run Flutter UI in development mode
cd flutter_app
flutter pub get
flutter run -d windows

# Run tests
cd flutter_app
flutter test

cd ..
python -m pytest tests/

# Build installer
build.bat installer
```

### Example: Batch Processing 50 TV Series Episodes

```python
from src.core.gpt_service import identify_all_media
from src.core.config import load_config

config = load_config()
files = [("01.mkv", "C:/Media/Breaking Bad/Season 01/01.mkv"), ...]

results = identify_all_media(files, config, parallel=True)
for r in results:
    print(f"{r.original_filename} → {r.title} S{r.season}E{r.episode} - {r.episode_title}")
```

---

## 🎯 Features in Detail

### 📺 **Media Identification** (Plex/Jellyfin/Emby Mode)

| Feature | Description |
|---------|-------------|
| **Multi-AI Support** | GPT-4o, Claude Sonnet 4, Gemini 2.0, or OpenRouter |
| **Web Search** | Live episode title lookup (TMDB/TheTVDB) |
| **Season Extraction** | From folder paths (S01, Season 1, Series 1, Staffel 1, etc.) |
| **Confidence Scoring** | 0-100 rating for each identification |
| **Special Handling** | Detects specials, interviews, behind-the-scenes, featurettes |
| **Subtitle Matching** | Auto-rename .srt, .ass, .vtt files alongside video |
| **Batch Processing** | 15-file batches with automatic retry on failure |
| **Parallel Processing** | 2-3 concurrent API calls for speed |

### 📁 **Platform Templates**

#### Plex (IMDB/TheTVDB)
```
Movies/
  ├── The Matrix (1999)/
  │   └── The Matrix (1999).mkv
TV Shows/
  ├── Breaking Bad (2008-2013)/
  │   ├── Season 01/
  │   │   └── Breaking Bad - S01E01 - Pilot.mkv
```

#### Jellyfin/Emby
```
Movies/
  ├── Inception (2010).mkv
TV Shows/
  ├── Breaking Bad/
  │   ├── Season 1/
  │   │   └── Breaking Bad S01E01 The Pilot.mkv
```

#### Generic Custom
```
TV/
  ├── breaking_bad_s01e01.mkv
  ├── breaking_bad_s01e02.mkv
```

### ⚡ **Performance Metrics** (v2.0.0)

| Operation | Time | Notes |
|-----------|------|-------|
| Scan 48 files | ~2s | Detects all media types |
| Identify 5 files | 15s | Includes web search |
| Identify 48 files (parallel) | 32s | 4 batches × 2 workers |
| **Cost per 100 files** | $0.10-0.30 | Depends on model/provider |

---

## 🔧 Configuration

### Default Settings
```json
{
  "llm_provider": "openai",
  "openai_model": "gpt-4o",
  "use_web_search": true,
  "gpt_batch_size": 15,
  "gpt_parallel_workers": 2,
  "platform": "generic",
  "mode": "media"
}
```

### Custom Prompt Example
```
Rename TV episodes to: {series} - S{season:02d}E{episode:02d} - {episode_title}
Include the year: ({year}) in the series folder name.
For specials, use Season 0 and descriptive titles.
```

---

## 📊 Supported Formats

### Video Formats
`.mkv` `.mp4` `.avi` `.mov` `.wmv` `.flv` `.webm` `.m4v` `.mpg` `.mpeg` `.ts` `.m2ts` `.vob` `.3gp` `.ogv` and more

### Audio Formats  
`.mp3` `.flac` `.wav` `.aac` `.m4a` `.ogg` `.opus` `.wma` `.alac` and more

### Subtitle Formats
`.srt` `.sub` `.ass` `.ssa` `.vtt` `.idx` `.smi` and more

### Generic Files
`.pdf` `.doc` `.zip` `.jpg` `.png` — basically anything!

---

## 🔐 Security & Privacy

- ✅ **No account required** — Just API keys from your chosen provider
- ✅ **No cloud storage** — Everything stays on your machine
- ✅ **Config in Documents** — Portable across machines
- ✅ **Open source** — Audit the code yourself!
- ✅ **Offline mode** — Fallback to standard API when web search unavailable

---

## 🆘 Troubleshooting

### "Invalid API Key"
- Verify the key is correct at your provider's dashboard
- OpenAI: https://platform.openai.com/account/api-keys
- Anthropic: https://console.anthropic.com/
- Make sure the API has billing enabled

### "Files not identified correctly"
- Check if the season folder name is recognized:
  - ✅ `Season 01`, `S01`, `Series 1`, `Staffel 1`, `Saison 1`
  - ❌ `S1` (too generic, could be ambiguous)
- Enable **Web Search** for episode title lookup
- Review confidence scores (lower scores = review before applying)

### "Truncated JSON response" (Large batches)
- Reduce batch size: Settings → Advanced → GPT Batch Size = 10
- Use gpt-4o model (better for large responses)

### "Rate limit exceeded"
- Wait a few seconds and retry
- Reduce parallel workers: Settings → Advanced → Workers = 1
- Consider upgrading your OpenAI tier

---

## 📦 What's New in v2.2.0

### 🎨 Major UI Overhaul
- ✅ **Flutter Desktop UI** — Complete rewrite using Flutter for native Windows desktop experience
  - Modern, responsive interface with smooth animations
  - Better performance and resource management
  - Improved UX with drag-and-drop support (coming soon)
- ✅ **JSON-Lines Bridge** — Clean Python-Flutter communication via `flutter_bridge.py`
  - Real-time progress updates during scanning and renaming
  - Proper cancellation support throughout the pipeline
  - Cleaner separation between UI and backend logic

### 🧪 Testing & Quality
- ✅ **Comprehensive Test Suite** — Added `tests/` directory with unit tests
  - Scanner tests for file discovery
  - Renamer tests for plan generation
  - Config tests for settings persistence
  - GPT service tests (mocked API calls)
- ✅ **Better Error Handling** — More robust error recovery in all modules

### 🏗️ Architecture Improvements
- ✅ **Modular Bridge Design** — `src/bridge/` handles all Flutter communication
- ✅ **Removed Legacy GUI** — Old PySimpleGUI code removed (`src/gui/`, `Renameify.py`)
- ✅ **Build System** — Streamlined `build.bat` for Flutter + PyInstaller packaging
- ✅ **No More Portable Build** — Focus on installer-only distribution

### 🔧 Previous Release (v2.1.1) Highlights
- ✅ **Test & Refresh button** — API Test button fetches live model list
- ✅ **Proper model names** — Models displayed with human-readable names
- ✅ **Plex Specials rules** — Correct folder consolidation
- ✅ **GUI scaling** — Better support for 1080p monitors

## 📦 What's New in v2.1.0

### 🚀 Major Improvements
- ✅ **Cancellation Support** — Cancel long-running LLM operations and renames gracefully
- ✅ **Updated Models** — Latest model support:
  - Claude Sonnet 4 (claude-sonnet-4-20250514)
  - Gemini 2.0 Flash (gemini-2.0-flash)
  - OpenAI GPT-4o maintained as default
- ✅ **Reduced Batch Size** — 12 files default (even better reliability than v2.0.0)
- ✅ **Enhanced GUI** — Better threading, progress tracking, and cancellation UI
- ✅ **Improved Error Handling** — More robust API error recovery

### ⚡ Performance (v2.1.0)
- ✅ **Faster cancellation** — 2-3 second interrupt on long batches
- ✅ **Better responsiveness** — GUI stays responsive during LLM calls
- ✅ **Parallel batch processing** — Process 4+ batches simultaneously
- ✅ **Optimized workers** — 2 concurrent workers for web search mode

### 📈 Quality
- ✅ **54+ unit tests** — Comprehensive test coverage
- ✅ **Season extraction** — 100% accurate from folder paths (supports 10+ languages)
- ✅ **Episode titles** — 80%+ success rate via web search
- ✅ **Specials detection** — Doctor Who, extras, behind-the-scenes all detected

### 🔄 Previous Release (v2.0.0) Highlights
- Fixed API truncation bug for large batches
- Exponential backoff for rate limit (429) errors
- Improved JSON recovery for partial responses
- Comprehensive documentation and testing

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Linux/Mac support
- [ ] Additional media server APIs
- [ ] Anime-specific naming support
- [ ] GUI improvements (dark theme, drag-drop)
- [ ] Translation support

### How to Contribute
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) file for details.

---

## 🙏 Credits & Thanks

**Built with:**
- 🤖 [OpenAI GPT-4o](https://openai.com/gpt-4) — AI model
- 🧠 [Anthropic Claude](https://www.anthropic.com/) — Alternative AI
- 🔍 [Google Gemini](https://deepmind.google/technologies/gemini/) — Another option
- 🐍 [Python 3.10+](https://www.python.org/) — Backend language
- 🎨 [Flutter 3.0+](https://flutter.dev/) — Cross-platform UI framework
- 📦 [PyInstaller](https://www.pyinstaller.org/) — Python to executable bundling

**Inspired by:**
- [Plex](https://www.plex.tv/) Media Server
- [Jellyfin](https://jellyfin.org/) Project
- [Emby](https://emby.media/) Media System

---

## 📞 Support & Contact

- 🐛 **Bug Reports** → [GitHub Issues](https://github.com/yourusername/renameify/issues)
- 💡 **Feature Requests** → [GitHub Discussions](https://github.com/yourusername/renameify/discussions)
- 📧 **Email** → [your-email@example.com]

---

<div align="center">

**Made with ❤️ for media enthusiasts**

[⭐ Star this repo if it helps!](https://github.com/yourusername/renameify) • [Report Issues](https://github.com/yourusername/renameify/issues) • [Fork & Contribute](https://github.com/yourusername/renameify/fork)

</div>

