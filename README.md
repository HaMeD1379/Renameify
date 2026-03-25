# 🎬 Renameify

<div align="center">

**Transform Your Media Library with AI-Powered Intelligence**

An advanced file renaming application powered by OpenAI GPT, Anthropic Claude, and Google Gemini. Intelligently identify, organize, and rename your media files (movies, TV series) or any files with custom naming patterns.

Perfect for **Plex** | **Jellyfin** | **Emby** | **Custom Libraries**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Made with ❤️](https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F-red)]()

</div>

---

## ✨ Features

### 🎯 **Media Mode** (Plex/Jellyfin/Emby/Generic)

#### Intelligent Media Recognition
- **AI-Powered Identification**: State-of-the-art language models analyze messy filenames and folder structures
- **Multi-Provider Support**: Choose between OpenAI GPT-4o, Anthropic Claude, or Google Gemini
- **Confidence Scoring**: Review low-confidence suggestions before applying changes
- **Batch Processing**: Handle hundreds of files in a single operation

#### Smart Organization
- **Platform-Optimized Naming**: Pre-configured naming templates for all major media server platforms
- **Season/Episode Detection**: Automatically extract season and episode information from folder hierarchies
- **Episode Title Lookup**: Integrated web search finds real episode titles from TMDB and TheTVDB
- **Subtitle File Matching**: Automatically renames associated .srt, .ass, .vtt subtitle files
- **Folder Restructuring**: Optionally reorganize files into proper folder hierarchies according to platform standards

#### Advanced Customization
- **Plex Agent Configuration**: Choose from:
  - Plex Movie (IMDB-based)
  - Plex Series (TheTVDB-based)
  - The Movie Database (TMDB)
  - HamaTV (for anime)
- **Scanner Selection**: Configure for Movie or TV Series libraries
- **Storage Optimization**: Support for multiple file formats (.mkv, .mp4, .avi, .m4v, etc.)

### 🎨 **Mass Rename Mode**

- **Universal File Support**: Rename any file type (.pdf, .doc, .zip, .jpg, etc.)
- **Batch Processing**: Handle multiple files with consistent naming patterns
- **Flexible Rules**: Define custom renaming rules using natural language

### 🧠 **Custom Prompt System**

- **Natural Language Patterns**: Define naming rules in plain English
- **Override Default Prompts**: Create specialized rules for unique use cases
- **Reusable Templates**: Save and apply custom prompts across multiple operations
- **Examples**:
  - `Rename music files to: Artist - Album - Title (Year).ext`
  - `Format documents as: [YY-MM-DD] - Title - Category.pdf`
  - `Organize photos: YYYY-MM-DD_HH-MM-SS_Location.jpg`

### 🔄 **Rollback & History Management**

- **Complete Undo Support**: Revert any rename operation back to original filenames
- **Operation Logs**: Full history of all rename operations with timestamps
- **Selective Rollback**: Choose specific operations to undo
- **Error Recovery**: Automatically recover from interrupted operations

### ⚡ **Performance & Integration**

- **Fast Processing**: Optimized batch requests reduce API calls and processing time
- **Network Path Support**: Works seamlessly with UNC paths (`\\server\share`)
- **Smart Folder Filtering**: Automatically skip non-media directories
- **Portable Configuration**: Settings stored in Windows Documents folder (works across machines)
- **Progress Tracking**: Real-time progress bars and operation counters

### 🔐 **Security & Safety**

- **Preview Before Apply**: Always review suggested renames before committing changes
- **Selective Processing**: Choose which files to rename from the GUI
- **Safe Rollback**: Complete history tracking for disaster recovery
- **API Key Protection**: Securely stores API keys with validation

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10 or higher**
- **At least one API key** from:
  - OpenAI (recommended for best results)
  - Anthropic Claude (excellent alternative)
  - Google Gemini (free tier available)

### Installation Steps

1. **Clone or download the repository**
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/renameify.git
   cd renameify
   ```

2. **Create a virtual environment** (optional but recommended)
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python Renameify.py
   ```

### 🔑 Get Your API Keys

**OpenAI (Recommended)**
1. Visit [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Go to API Keys → Create new secret key
4. Copy the key (save it securely!)

**Anthropic Claude**
1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to API Keys → Create new key
4. Copy the key

**Google Gemini**
1. Visit [ai.google.dev](https://ai.google.dev)
2. Sign in with your Google account
3. Create new API key
4. Copy the key

---

## ⚙️ Configuration

Configuration is automatically stored in your Windows Documents folder, so you can run Renameify from anywhere. Your settings persist across sessions.

### Config File Location
```
C:\Users\<YourUsername>\Documents\Renameify\renameify_config.json
```

### Initial Setup Wizard

When you first launch Renameify:

1. **API Configuration**
   - Select your preferred LLM provider (OpenAI, Claude, or Gemini)
   - Enter your API key
   - Click "Test Connection" to verify

2. **Platform Selection**
   - Choose your media server (Plex, Jellyfin, Emby, or Generic)
   - Configure agent and scanner settings (Plex mode)

3. **Folder Preferences**
   - Set default starting folder
   - Enable/disable smart folder filtering
   - Configure exclusion patterns

### Manual Configuration

1. **Launch Renameify**: `python Renameify.py`
2. **Go to Settings Tab**
3. **Configure API Provider**
   - Select OpenAI, Claude, or Gemini
   - Paste your API key
   - Click "Test" to verify connectivity
4. **Save Configuration**

### Configuration Options

```json
{
  "api_provider": "openai",
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "platform": "plex",
  "plex_agent": "tmdb",
  "plex_scanner": "tv",
  "smart_filter": true,
  "default_folder": "C:\\path\\to\\media",
  "enable_web_search": true,
  "confidence_threshold": 0.7
}
```

---

## 📖 Usage Guide

### Workflow Overview

```
Launch Renameify → Choose Mode → Select Folder → Scan Files → Review Suggestions → Apply Changes → (Optional) Rollback
```

### 🎬 Media Mode (Step-by-Step)

Perfect for movies and TV series organization.

**Step 1: Select Media Mode**
- Launch the application
- Click the "Media (Plex/Jellyfin)" tab
- Choose your platform: Plex, Jellyfin, Emby, or Generic

**Step 2: Configure Platform Settings** (Optional)
- For Plex: Click "Plex Options" to select agent and scanner
  - **Agent Options**: Plex Movie, Plex Series, TMDB, HamaTV
  - **Scanner Options**: Movie Scanner or TV Series Scanner
- Other platforms have pre-configured settings

**Step 3: Select Folder**
- Click "Browse" to choose the directory with files to rename
- Supports local drives and network paths (UNC paths)

**Step 4: Scan & Analyze**
- Click "Start Scan"
- Renameify analyzes all files and generates rename suggestions
- Progress bar shows real-time status

**Step 5: Review Suggestions**
- View proposed renames in the results table
- Check the "Suggested Name" column
- Review confidence scores for each guess
- Low confidence items are highlighted for manual review

**Step 6: Apply Changes**
- Select files you want to rename (use checkboxes)
- Click "Apply Renames"
- Confirm the operation in the dialog
- Changes are applied and logged

**Step 7: Verify Results**
- Check that files were renamed correctly
- Folder structure is created if specified
- Subtitles are renamed alongside video files

### 📁 Mass Rename Mode

For renaming any file type with flexible patterns.

1. **Switch to Mass Rename Tab**
2. **Select Folder** with files to rename
3. **Enter Naming Pattern** (optional)
   - Or use AI suggestions with custom prompt
4. **Click Start Scan**
5. **Review Suggestions**
6. **Apply Renames**

### 🧠 Custom Prompt Override

Define your own naming logic using natural language.

**Examples:**

**Music Files**
```
Rename music files to: Artist - Album - Title (Year).ext
Keep only alphanumeric characters and spaces
Use Title Case for all words
```

**Documents**
```
Rename PDFs to: [YYYY-MM-DD] - DocumentTitle - Category.pdf
Extract date from file creation date
Organize by document category
```

**Photos**
```
Rename photos to: YYYY-MM-DD_HH-MM-SS_Location.jpg
Extract timestamp from EXIF data
Add location information if available
```

**How to Use:**
1. Go to any mode tab
2. Click "Custom Prompt..."
3. Enter your naming instructions
4. Click "Use This Prompt"
5. Continue with normal workflow

### 📊 Platform-Specific Examples

#### Plex Media Server
Plex expects very specific naming conventions to work properly.

**Movie Example:**
```
Before:  movies_hd.mkv
After:   Movies/Movie Title (2023)/Movie Title (2023).mkv
```

**TV Series Example:**
```
Before:  show.s01e01.720p.mkv
After:   TV Shows/Show Name (2020)/Season 01/Show Name - S01E01 - Episode Title.mkv
```

**Configuration:**
- Agent: TMDB (recommended)
- Scanner: TV Series Scanner (for shows)

#### Jellyfin Media Server
Jellyfin uses similar but slightly different naming conventions.

**Movie Format:**
```
Movie Title (2023)/Movie Title (2023).mkv
```

**Series Format:**
```
Show Name (2020)/Season 01/Show Name S01E01 Episode Title.mkv
```

#### Emby Media Server
Emby supports various naming conventions.

**Recommended Format:**
```
Movies: Movie Title (2023)/Movie Title (2023).mkv
Shows: Show Name (2020)/Season 01/Show Name S01E01 - Episode Title.mkv
```

#### Generic/Custom Organization
When using Generic mode, you can organize files any way you prefer:

```
[Category]/[Year]/Title Format.mkv
```

### 🔄 History & Rollback

Every rename operation is logged and can be reversed.

**To Rollback:**
1. Go to the "History" tab
2. Select the operation you want to undo
3. Click "Rollback Selected"
4. Confirm the operation
5. All files are restored to original names and locations

**What's Tracked:**
- Original filename
- New filename
- Folder changes
- Timestamp
- Operation status
- Error information (if any)

---

## 🏗️ Project Architecture

### Directory Structure

```
Renameify/
├── Renameify.py                 # Main entry point with CLI support
│
├── src/
│   ├── __init__.py             # Package initialization
│   │
│   ├── core/                   # Core functionality modules
│   │   ├── config.py           # Configuration management & validation
│   │   ├── scanner.py          # File scanning & discovery
│   │   ├── gpt_service.py      # Multi-provider LLM integration
│   │   ├── renamer.py          # Rename plan generation & execution
│   │   └── rollback.py         # Undo/rollback & history management
│   │
│   ├── gui/                    # Graphical user interface
│   │   └── app.py              # Main tkinter GUI application
│   │
│   ├── cli/                    # Command-line interface
│   │   └── commands.py         # CLI command handlers
│   │
│   ├── platforms/              # Platform-specific configurations
│   │   ├── base.py             # Base platform class (abstract)
│   │   ├── plex.py             # Plex naming & agent configuration
│   │   ├── jellyfin.py         # Jellyfin naming conventions
│   │   ├── emby.py             # Emby naming conventions
│   │   └── generic.py          # Generic/custom naming patterns
│   │
│   ├── prompts/                # AI prompt management
│   │   ├── builtin.py          # Built-in platform prompts
│   │   └── manager.py          # Custom prompt storage & loading
│   │
│   └── utils/                  # Utility functions
│       ├── drive_utils.py      # Drive enumeration & path handling
│       ├── folder_filter.py    # Smart folder filtering logic
│       └── folder_fixer.py     # Folder structure corrections
│
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── LICENSE                     # MIT License
```

### Architecture Highlights

**Multi-Provider LLM Support**
- Abstract interface for different LLM providers
- Easy to add new providers (OpenRouter, Cohere, etc.)
- Automatic fallback to backup providers

**Platform Abstraction**
- Base class defines interface for all platforms
- Each platform inherits and customizes:
  - Naming conventions
  - Folder structures
  - Metadata requirements

**Safety-First Design**
- All changes logged with full rollback capability
- Preview system prevents accidental changes
- Atomic operations with error recovery

---

## 📋 Naming Conventions Reference

### Movies

| Platform | Folder Structure | File Format |
|----------|------------------|-------------|
| **Plex** | `Movie Title (2023)` | `Movie Title (2023).mkv` |
| **Jellyfin** | `Movie Title (2023)` | `Movie Title (2023).mkv` |
| **Emby** | `Movie Title (2023)` | `Movie Title (2023).mkv` |
| **Generic** | `Movie Title [2023]` | `Movie Title [2023].mkv` |

### TV Series

| Platform | Series Folder | Season Folder | Episode Format |
|----------|---------------|---------------|-----------------|
| **Plex** | `Show Name (2020)` | `Season 01` | `Show Name - S01E01 - Title.mkv` |
| **Jellyfin** | `Show Name (2020)` | `Season 01` | `Show Name S01E01 Title.mkv` |
| **Emby** | `Show Name (2020)` | `Season 01` | `Show Name S01E01 - Title.mkv` |
| **Generic** | `Show Name [2020]` | `Season 01` | `Show Name S01E01 - Title.mkv` |

### Supported File Extensions

**Video Files:**
- `.mkv` (Matroska)
- `.mp4` (MPEG-4)
- `.avi` (Audio Video Interleave)
- `.m4v` (iTunes Protected)
- `.mov` (QuickTime)
- `.flv` (Flash Video)
- `.wmv` (Windows Media)

**Subtitle Files:**
- `.srt` (SubRip)
- `.ass` / `.ssa` (Advanced SubStation Alpha)
- `.vtt` (WebVTT)
- `.sub` (SubViewer)

**Metadata:**
- `.nfo` (Kodi metadata)
- `.json` (Generic metadata)

---

## 💰 API Costs & Performance

### Cost Estimates

**OpenAI (gpt-4o-mini - Recommended)**
- ~$0.00015 per file
- 100 files: ~$0.015
- 1,000 files: ~$0.15
- 10,000 files: ~$1.50

**Anthropic Claude (claude-3-haiku)**
- Similar or lower costs
- Excellent accuracy for filenames

**Google Gemini**
- Free tier with usage limits
- Low cost for paid tier
- Good performance for batch operations

### Performance Metrics

**Batch Processing:**
- Single file: ~2-3 seconds (including API call)
- 10 files: ~5-10 seconds
- 100 files: ~30-60 seconds
- 1000 files: ~5-10 minutes

**Optimizations:**
- Batched API requests reduce latency
- Parallel processing for non-sequential operations
- Caching of repeated patterns

---

## 🐛 Troubleshooting

### General Issues

**Problem: "API Key not configured"**
```
Solution:
1. Go to Settings tab
2. Enter your API key for your chosen provider
3. Click "Test Connection" to verify
4. Click "Save"
```

**Problem: "Connection timeout"**
```
Solution:
1. Check internet connection
2. Verify API key is valid
3. Try a different API provider
4. Check firewall/proxy settings
```

**Problem: Application won't start**
```
Solution:
1. Ensure Python 3.10+ is installed: python --version
2. Install dependencies: pip install -r requirements.txt
3. Run from command line to see error: python Renameify.py
```

### File Scanning Issues

**Problem: "No media files found"**
```
Solution:
1. Check that the directory contains video files (.mkv, .mp4, etc.)
2. Disable "Smart Folder Filter" (Settings → Advanced)
3. Check folder isn't in the exclusion list
4. Verify you have read permissions
5. For network paths, ensure the UNC path is correct: \\server\share
```

**Problem: "Permission denied" errors**
```
Solution:
1. Run as Administrator (right-click → Run as administrator)
2. Check file/folder permissions
3. Close other applications using the files
4. For network shares, verify credentials and share permissions
```

### Rename & Processing Issues

**Problem: "Low confidence results"**
```
Solution:
1. Files with scene release names need manual review
2. Try the custom prompt for specific patterns
3. Use a different AI provider (may give better results)
4. Verify file naming includes enough context
```

**Problem: "Duplicate filename after rename"**
```
Solution:
1. Renameify prevents overwriting existing files
2. Review files in the folder before renaming
3. Use the custom prompt to add differentiators
4. Use rollback if needed: History → Rollback Selected
```

**Problem: "Folder structure not created"**
```
Solution:
1. Check "Create Folders" option is enabled
2. Verify write permissions on the directory
3. Check disk space is available
4. For network paths, verify network access
```

### Rollback & History Issues

**Problem: "Cannot rollback - history missing"**
```
Solution:
1. Rollback files must not have been manually moved
2. Check that source files still exist
3. If overwritten, use file recovery software
4. Note: Rollback only works for operations within Renameify
```

**Problem: "Operation log corrupted"**
```
Solution:
1. Go to Documents\Renameify\history
2. Find the corresponding .json file
3. Manually restore from backup (if available)
4. Contact support with the error details
```

### API & Configuration Issues

**Problem: "API key rejected"**
```
Solution:
1. Verify you copied the ENTIRE key without extra spaces
2. Check the key hasn't expired or been revoked
3. Try creating a new key in your provider's dashboard
4. Ensure you're using the correct key (not organization key)
```

**Problem: "Config not saving"**
```
Solution:
1. Check Documents folder is accessible
2. Run as Administrator if on restricted user account
3. Verify disk space available
4. Check Documents\Renameify folder permissions
5. Try clearing config and reconfiguring
```

**Problem: "Model not available"**
```
Solution:
1. Check API provider status page
2. Verify your account has access to the model
3. Check API quota hasn't been exceeded
4. Try a different available model
```

---

## 🔧 Advanced Configuration

### Environment Variables

Create a `.env` file in the Renameify directory:

```env
RENAMEIFY_API_KEY=your_api_key_here
RENAMEIFY_PROVIDER=openai
RENAMEIFY_MODEL=gpt-4o-mini
RENAMEIFY_CONFIG_DIR=C:\path\to\custom\config
```

### Command-Line Usage

```bash
# Show help
python Renameify.py --help

# Show version
python Renameify.py --version

# Open config folder
python Renameify.py --config
```

### Batch Operations

For processing multiple folders, you can run Renameify multiple times:

```bash
for /d %F in (D:\Media\*) do (
    echo Processing %F
    python Renameify.py --folder "%F" --apply --mode media
)
```

---

## 🚀 Building Standalone Executable

Convert Renameify to a standalone .exe file (no Python installation required):

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --windowed --name Renameify --icon app.ico Renameify.py

# Output will be in: dist/Renameify.exe
```

**Distribution:**
- Copy `dist/Renameify.exe` to users
- No Python installation needed
- Config stored in Documents\Renameify (portable)
- File size: ~80-120 MB (includes Python runtime)

---

## 📚 API Reference

### Supported Providers

**OpenAI**
```python
provider: "openai"
models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
```

**Anthropic**
```python
provider: "anthropic"
models: ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
```

**Google Gemini**
```python
provider: "google"
models: ["gemini-1.5-pro", "gemini-1.5-flash"]
```

---

## 📄 File Format Examples

### Input: Messy Files

```
Action.Movie.2024.2160p.WEB-DL.x265-RELEASE.mkv
TheShowS05E12.1080p.HDTV.x264-GROUP.mkv
series.name.2020.s03e04.episode.name.mkv
Movie(2023)DVDRip.avi
```

### Output: Organized by Plex

```
Movies/
├── Action Movie (2024)/
│   └── Action Movie (2024).mkv

TV Shows/
├── The Show (2023)/
│   └── Season 05/
│       └── The Show - S05E12 - Episode Title.mkv
│       └── The Show - S05E12 - Episode Title.srt
├── Series Name (2020)/
│   └── Season 03/
│       └── Series Name - S03E04 - Episode Name.mkv
```

---

## 🤝 Contributing

Contributions are welcome! Areas for contribution:

- New platform support (Kaleidescape, etc.)
- Additional AI provider integration
- Improved episode/movie detection
- GUI enhancements
- Documentation improvements
- Bug fixes and performance optimization

**To contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI** - For GPT models and API
- **Anthropic** - For Claude models
- **Google** - For Gemini API
- **TheTVDB & TMDB** - For media metadata
- **Plex, Jellyfin, Emby** - For media server inspiration
- **Community** - For feedback and bug reports

---

## 📞 Support & Feedback

- **Report Issues**: Open an issue on GitHub
- **Feature Requests**: Discuss in GitHub Discussions
- **Documentation**: Check the wiki for additional guides
- **Community**: Join our Discord community (coming soon)

---

<div align="center">

**Made with ❤️ for media organization enthusiasts**

**[⬆ Back to Top](#-renameify)**

</div>
