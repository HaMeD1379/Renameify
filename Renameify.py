#!/usr/bin/env python3
"""
Renameify - AI-Powered File Renaming Tool

A smart file renaming application that uses OpenAI GPT to identify
and rename media files (movies, TV series) or any files with custom patterns.

Features:
- Platform modes (Plex, Jellyfin, Emby, Generic)
- Custom prompt override for naming patterns
- Mass rename mode for any file types
- Plex Agent and Scanner options
- Config stored in Windows Documents folder
- Full undo/rollback support

Usage:
    python Renameify.py          Launch GUI application
    python Renameify.py --help   Show help message
"""
import sys
import os
from pathlib import Path


def get_base_path():
    """Get the base path for resources - handles both dev and PyInstaller bundled modes."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


# Add src directory to path
BASE_PATH = get_base_path()
SRC_DIR = BASE_PATH / "src"
sys.path.insert(0, str(SRC_DIR))


def main():
    """Main entry point for Renameify."""
    # Check for command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--help", "-h"):
            print(__doc__)
            print("\nOptions:")
            print("  --help, -h     Show this help message")
            print("  --version, -v  Show version information")
            print("  --config       Open config folder")
            print("\nRun without arguments to launch the GUI.")
            return 0
        elif arg in ("--version", "-v"):
            from src import __version__, __app_name__
            print(f"{__app_name__} v{__version__}")
            return 0
        elif arg == "--config":
            from core.config import get_config_dir
            config_dir = get_config_dir()
            print(f"Config directory: {config_dir}")
            os.startfile(config_dir)
            return 0

    # Launch GUI
    try:
        from gui.app import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"Error: Could not import GUI module: {e}")
        print("Make sure all dependencies are installed: pip install openai")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
