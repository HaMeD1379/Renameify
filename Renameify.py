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


BASE_PATH = get_base_path()

# In dev mode, add src/ to path so `from core.config import ...` etc. work.
# In frozen mode, PyInstaller already collected all modules via --paths=src,
# so they live in the PYZ archive and are importable without sys.path hacks.
if not getattr(sys, 'frozen', False):
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
            from core.config import APP_NAME, APP_VERSION
            print(f"{APP_NAME} v{APP_VERSION}")
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
        _report_error(f"Could not import GUI module: {e}\n"
                      "Make sure all dependencies are installed: pip install openai")
        return 1
    except Exception as e:
        import traceback
        _report_error(f"{e}\n\n{traceback.format_exc()}")
        return 1

    return 0


def _report_error(message: str):
    """Show an error to the user — handles both console and windowed frozen builds."""
    print(f"Error: {message}")
    if getattr(sys, 'frozen', False):
        # In a windowed frozen build there is no console, so write a crash log
        # and try to pop up a message box.
        try:
            log_path = Path(os.environ.get("USERPROFILE", ".")) / "Documents" / "Renameify" / "crash.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(message, encoding="utf-8")
        except Exception:
            pass
        try:
            import tkinter as _tk
            import tkinter.messagebox as _mb
            _root = _tk.Tk()
            _root.withdraw()
            _mb.showerror("Renameify - Startup Error", message[:1500])
            _root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
