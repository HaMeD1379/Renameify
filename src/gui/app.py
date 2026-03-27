"""
Renameify - AI-Powered File Renaming Tool
Main GUI Application

Features:
- Platform modes (Plex, Jellyfin, Emby, Generic)
- Custom prompt override for naming patterns
- Mass rename mode for any files
- Plex Agent and Scanner options
- Config stored in Windows Documents folder
"""
import os
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from pathlib import Path
from datetime import datetime


def get_base_path():
    """Get the base path for resources - handles both dev and PyInstaller bundled modes."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent.parent


# Add src to path for imports
sys.path.insert(0, str(get_base_path()))

from core.config import (
    load_config, save_config, get_api_key, set_api_key,
    get_config_dir, add_exclusion, remove_exclusion, list_exclusions,
    set_platform, get_custom_prompt, set_custom_prompt, add_recent_path, get_recent_paths,
    PLATFORM_PLEX, PLATFORM_JELLYFIN, PLATFORM_EMBY, PLATFORM_GENERIC,
    AVAILABLE_MODELS, get_available_models, get_current_model, set_current_model,
    fetch_available_models, clear_model_cache
)
from core.scanner import scan_directory, ScanProgress
from core.gpt_service import identify_all_media, GPTProgress
from core.renamer import generate_rename_plan, execute_rename_plan, execute_rollback, RenamePlan
from core.rollback import list_manifests, load_manifest
from platforms.plex import PLEX_AGENTS, PLEX_SCANNERS

# Try to import metadata module (optional)
try:
    from core.metadata import read_metadata, write_metadata, is_mutagen_available, FileMetadata
    METADATA_AVAILABLE = True
except ImportError:
    METADATA_AVAILABLE = False


APP_NAME = "Renameify"
APP_VERSION = "2.0.0"


class DetailedProgressPanel(ttk.Frame):
    """Progress panel with status information."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.progress_var = tk.DoubleVar(value=0)
        self.bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100, length=400)
        self.bar.pack(fill="x", pady=(0, 5))

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self, textvariable=self.status_var, font=("Segoe UI", 10, "bold"))
        self.status_label.pack(anchor="w")

        self.detail_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.detail_var, font=("Consolas", 9)).pack(anchor="w")

    def update_progress(self, percent: float, status: str = None, details: str = None):
        self.progress_var.set(percent)
        if status:
            self.status_var.set(status)
        if details:
            self.detail_var.set(details)


class CustomPromptDialog(tk.Toplevel):
    """Dialog for entering custom prompt override."""

    def __init__(self, parent, current_prompt: str = ""):
        super().__init__(parent)
        self.title("Custom Prompt Override")
        self.geometry("700x500")
        self.transient(parent)
        self.grab_set()

        self.result = None

        # Instructions
        ttk.Label(
            self,
            text="Enter a custom prompt to override the default naming pattern.\n"
                 "Your prompt will be sent to GPT to determine how files should be renamed.",
            wraplength=650,
            justify="left"
        ).pack(padx=15, pady=15)

        # Example label
        example_frame = ttk.LabelFrame(self, text="Example Prompts", padding=10)
        example_frame.pack(fill="x", padx=15, pady=5)

        examples = [
            "Rename files to format: Artist - Song Title (Year).ext",
            "Use lowercase with underscores: my_file_name.ext",
            "Add date prefix: YYYY-MM-DD_filename.ext",
            "Clean up scene release names and use Plex naming: Show Name - S01E01 - Episode Title.ext"
        ]
        for ex in examples:
            ttk.Label(example_frame, text=f"- {ex}", font=("Consolas", 9)).pack(anchor="w")

        # Text area
        ttk.Label(self, text="Your Custom Prompt:").pack(anchor="w", padx=15, pady=(10, 5))

        self.text = scrolledtext.ScrolledText(self, height=12, width=80, font=("Consolas", 10))
        self.text.pack(fill="both", expand=True, padx=15, pady=5)
        if current_prompt:
            self.text.insert("1.0", current_prompt)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=15, pady=15)

        ttk.Button(btn_frame, text="Save & Enable", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear & Disable", command=self._clear).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)

    def _save(self):
        self.result = ("save", self.text.get("1.0", "end-1c").strip())
        self.destroy()

    def _clear(self):
        self.result = ("clear", "")
        self.destroy()


class PlexOptionsDialog(tk.Toplevel):
    """Dialog for Plex Agent and Scanner options (Advanced - Optional)."""

    def __init__(self, parent, current_agent: str, current_scanner: str, enabled: bool = False):
        super().__init__(parent)
        self.title("Plex Options (Advanced)")
        self.geometry("550x500")
        self.transient(parent)
        self.grab_set()

        self.result = None

        # Main info
        ttk.Label(
            self,
            text="These are optional advanced settings for Plex compatibility.\n"
                 "The renamer works perfectly without these options.",
            wraplength=500,
            foreground="gray"
        ).pack(padx=15, pady=10)

        # Enable checkbox
        self.enabled_var = tk.BooleanVar(value=enabled)
        enable_frame = ttk.Frame(self)
        enable_frame.pack(fill="x", padx=15, pady=5)

        self.enable_check = ttk.Checkbutton(
            enable_frame,
            text="Enable Plex-specific options (Advanced)",
            variable=self.enabled_var,
            command=self._toggle_options
        )
        self.enable_check.pack(anchor="w")

        # Options frame (can be disabled)
        self.options_frame = ttk.Frame(self)
        self.options_frame.pack(fill="both", expand=True, padx=15, pady=10)

        # Agent selection
        agent_frame = ttk.LabelFrame(self.options_frame, text="Plex Agent (Optional)", padding=10)
        agent_frame.pack(fill="x", pady=5)

        self.agent_var = tk.StringVar(value=current_agent if current_agent else "none")

        # Add "None" option
        rb_none = ttk.Radiobutton(
            agent_frame,
            text="None - Use default naming (Recommended)",
            value="none",
            variable=self.agent_var
        )
        rb_none.pack(anchor="w", pady=2)

        for key, agent in PLEX_AGENTS.items():
            rb = ttk.Radiobutton(
                agent_frame,
                text=f"{agent['name']} - {agent['description']}",
                value=key,
                variable=self.agent_var
            )
            rb.pack(anchor="w", pady=2)

        # Scanner selection
        scanner_frame = ttk.LabelFrame(self.options_frame, text="Plex Scanner (Optional)", padding=10)
        scanner_frame.pack(fill="x", pady=5)

        self.scanner_var = tk.StringVar(value=current_scanner if current_scanner else "none")

        # Add "None" option
        rb_none = ttk.Radiobutton(
            scanner_frame,
            text="None - Use default naming (Recommended)",
            value="none",
            variable=self.scanner_var
        )
        rb_none.pack(anchor="w", pady=2)

        for key, scanner in PLEX_SCANNERS.items():
            rb = ttk.Radiobutton(
                scanner_frame,
                text=f"{scanner['name']} - {scanner['description']}",
                value=key,
                variable=self.scanner_var
            )
            rb.pack(anchor="w", pady=2)

        # Info label
        ttk.Label(
            self.options_frame,
            text="Tip: Most users get perfect results without these options.\n"
                 "Only use if you have specific Plex library requirements.",
            wraplength=500,
            foreground="blue",
            font=("Segoe UI", 9)
        ).pack(pady=10)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=15, pady=15)

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)

        # Initial state
        self._toggle_options()

    def _toggle_options(self):
        """Enable/disable options based on checkbox."""
        state = "normal" if self.enabled_var.get() else "disabled"
        for child in self.options_frame.winfo_children():
            self._set_state_recursive(child, state)

    def _set_state_recursive(self, widget, state):
        """Recursively set state on all children."""
        try:
            widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._set_state_recursive(child, state)

    def _save(self):
        enabled = self.enabled_var.get()
        if enabled:
            agent = self.agent_var.get()
            scanner = self.scanner_var.get()
            # Convert "none" back to empty string
            agent = "" if agent == "none" else agent
            scanner = "" if scanner == "none" else scanner
        else:
            agent = ""
            scanner = ""
        self.result = (agent, scanner, enabled)
        self.destroy()


class MetadataDialog(tk.Toplevel):
    """Dialog for viewing and editing file metadata."""

    def __init__(self, parent, file_path: str):
        super().__init__(parent)
        self.title("File Metadata")
        self.geometry("600x550")
        self.transient(parent)
        self.grab_set()

        self.file_path = file_path
        self.result = None
        self.edits = {}

        if not METADATA_AVAILABLE:
            ttk.Label(
                self,
                text="Metadata module not available.\nInstall mutagen: pip install mutagen",
                foreground="red"
            ).pack(padx=20, pady=20)
            ttk.Button(self, text="Close", command=self.destroy).pack(pady=10)
            return

        # File info
        ttk.Label(
            self,
            text=f"File: {Path(file_path).name}",
            font=("Segoe UI", 10, "bold"),
            wraplength=560
        ).pack(padx=15, pady=10, anchor="w")

        # Read metadata
        self.metadata = read_metadata(file_path)

        if not self.metadata.is_readable:
            ttk.Label(
                self,
                text=f"Error reading metadata: {self.metadata.error}",
                foreground="red"
            ).pack(padx=15, pady=10)
            ttk.Button(self, text="Close", command=self.destroy).pack(pady=10)
            return

        # Status info
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=15, pady=5)

        status = "Has metadata" if self.metadata.has_metadata else "No metadata found"
        ttk.Label(
            status_frame,
            text=f"Type: {self.metadata.file_type.title()} | Status: {status}",
            foreground="green" if self.metadata.has_metadata else "orange"
        ).pack(anchor="w")

        # Create scrollable frame for metadata fields
        canvas_frame = ttk.LabelFrame(self, text="Metadata Fields", padding=10)
        canvas_frame.pack(fill="both", expand=True, padx=15, pady=10)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self.fields_frame = ttk.Frame(canvas)

        self.fields_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.fields_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create editable fields
        self._create_fields()

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=15, pady=15)

        if is_mutagen_available():
            ttk.Button(btn_frame, text="Save Changes", command=self._save).pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side="right", padx=5)

    def _create_fields(self):
        """Create editable metadata fields."""
        display_data = self.metadata.get_display_dict()

        # Define editable fields
        editable_fields = [
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
            ("Album Artist", "album_artist"),
            ("Year", "year"),
            ("Genre", "genre"),
            ("Track", "track_number"),
            ("Show", "show_name"),
            ("Season", "season"),
            ("Episode", "episode"),
        ]

        self.entry_vars = {}
        row = 0

        for display_name, field_name in editable_fields:
            current_value = getattr(self.metadata, field_name, None)
            if current_value is not None or field_name in ["title", "artist", "album", "year"]:
                ttk.Label(self.fields_frame, text=f"{display_name}:", width=15).grid(
                    row=row, column=0, sticky="w", padx=5, pady=3
                )

                var = tk.StringVar(value=str(current_value) if current_value else "")
                entry = ttk.Entry(self.fields_frame, textvariable=var, width=40)
                entry.grid(row=row, column=1, sticky="w", padx=5, pady=3)

                self.entry_vars[field_name] = var
                row += 1

        # Read-only fields
        readonly_fields = [
            ("Duration", self.metadata.duration_seconds,
             lambda v: f"{int(v // 60)}:{int(v % 60):02d}" if v else None),
            ("Bitrate", self.metadata.bitrate,
             lambda v: f"{v // 1000}kbps" if v else None),
            ("Sample Rate", self.metadata.sample_rate,
             lambda v: f"{v}Hz" if v else None),
            ("Codec", self.metadata.codec, str),
        ]

        if any(value for _, value, _ in readonly_fields):
            ttk.Separator(self.fields_frame, orient="horizontal").grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=10
            )
            row += 1

            ttk.Label(
                self.fields_frame,
                text="Technical Info (Read-Only):",
                font=("Segoe UI", 9, "bold")
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
            row += 1

            for display_name, value, formatter in readonly_fields:
                if value:
                    formatted = formatter(value)
                    if formatted:
                        ttk.Label(self.fields_frame, text=f"{display_name}:", width=15).grid(
                            row=row, column=0, sticky="w", padx=5, pady=2
                        )
                        ttk.Label(self.fields_frame, text=formatted).grid(
                            row=row, column=1, sticky="w", padx=5, pady=2
                        )
                        row += 1

    def _save(self):
        """Save metadata changes."""
        updates = {}
        for field_name, var in self.entry_vars.items():
            new_value = var.get().strip()
            old_value = getattr(self.metadata, field_name, None)

            if new_value != (str(old_value) if old_value else ""):
                if new_value:
                    # Convert to appropriate type
                    if field_name in ["year", "season", "episode", "track_number"]:
                        try:
                            updates[field_name] = int(new_value)
                        except ValueError:
                            pass
                    else:
                        updates[field_name] = new_value
                elif old_value:
                    updates[field_name] = None  # Clear field

        if updates:
            success = write_metadata(self.file_path, updates)
            if success:
                messagebox.showinfo("Success", "Metadata updated successfully!")
                self.result = updates
            else:
                messagebox.showerror("Error", "Failed to write metadata.\nFile format may not support writing.")
        else:
            messagebox.showinfo("Info", "No changes to save.")

        self.destroy()


class RenameifyGUI:
    """Main GUI application for Renameify."""

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} - AI-Powered File Renaming")
        self.root.geometry("1200x850")
        self.root.minsize(1000, 750)

        # Variables
        self.current_path = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.smart_filter_var = tk.BooleanVar(value=True)
        self.include_low_var = tk.BooleanVar(value=False)
        self.platform_var = tk.StringVar(value=PLATFORM_GENERIC)
        self.mode_var = tk.StringVar(value="media")  # media or mass
        self.custom_prompt_enabled = tk.BooleanVar(value=False)

        # State
        self.current_plan = None
        self.media_files = []
        self.media_info = []
        self.is_processing = False
        self.selection_state = {}

        # Message queue
        self.msg_queue = queue.Queue()

        # Create UI
        self._create_ui()
        self._load_config()

        # Start message processor
        self.root.after(100, self._process_messages)

    def _create_ui(self):
        """Create the main UI."""
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Header with title and mode selection
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 15))

        ttk.Label(
            header_frame,
            text=f"{APP_NAME}",
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        ttk.Label(
            header_frame,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 10)
        ).pack(side="left", padx=(5, 20))

        # Mode selection
        mode_frame = ttk.Frame(header_frame)
        mode_frame.pack(side="left", padx=20)

        ttk.Label(mode_frame, text="Mode:").pack(side="left", padx=(0, 5))
        ttk.Radiobutton(
            mode_frame, text="Media (Plex/Jellyfin)",
            variable=self.mode_var, value="media",
            command=self._on_mode_change
        ).pack(side="left", padx=5)
        ttk.Radiobutton(
            mode_frame, text="Mass Rename (Any Files)",
            variable=self.mode_var, value="mass",
            command=self._on_mode_change
        ).pack(side="left", padx=5)

        # Platform selection (for media mode)
        self.platform_frame = ttk.Frame(header_frame)
        self.platform_frame.pack(side="left", padx=20)

        ttk.Label(self.platform_frame, text="Platform:").pack(side="left", padx=(0, 5))
        self.platform_combo = ttk.Combobox(
            self.platform_frame,
            textvariable=self.platform_var,
            values=["Generic", "Plex", "Jellyfin", "Emby"],
            state="readonly",
            width=12
        )
        self.platform_combo.pack(side="left", padx=5)
        self.platform_combo.bind("<<ComboboxSelected>>", self._on_platform_change)

        # Plex options button
        self.plex_options_btn = ttk.Button(
            self.platform_frame,
            text="Plex Options...",
            command=self._show_plex_options
        )
        self.plex_options_btn.pack(side="left", padx=5)
        self.plex_options_btn.pack_forget()  # Hidden by default

        # Custom prompt button
        ttk.Button(
            header_frame,
            text="Custom Prompt...",
            command=self._show_custom_prompt
        ).pack(side="right", padx=5)

        self.custom_prompt_indicator = ttk.Label(
            header_frame,
            text="",
            foreground="green"
        )
        self.custom_prompt_indicator.pack(side="right", padx=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        self._create_scan_tab()
        self._create_history_tab()
        self._create_settings_tab()

        # Progress panel
        progress_group = ttk.LabelFrame(main_frame, text="Status & Progress", padding="10")
        progress_group.pack(fill="x")
        self.progress_panel = DetailedProgressPanel(progress_group)
        self.progress_panel.pack(fill="x")

    def _create_scan_tab(self):
        """Create the scan and rename tab."""
        scan_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(scan_frame, text="Scan & Rename")

        # Path selection
        path_frame = ttk.LabelFrame(scan_frame, text="Target Directory", padding="10")
        path_frame.pack(fill="x", pady=(0, 15))

        input_frame = ttk.Frame(path_frame)
        input_frame.pack(fill="x", expand=True)

        self.path_combo = ttk.Combobox(input_frame, textvariable=self.current_path, width=80)
        self.path_combo.pack(side="left", fill="x", expand=True)

        ttk.Button(input_frame, text="Browse...", command=self._browse_directory).pack(side="left", padx=(10, 0))

        # Options
        opts_frame = ttk.Frame(path_frame)
        opts_frame.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(
            opts_frame,
            text="Smart Folder Filter (Skip non-media folders)",
            variable=self.smart_filter_var
        ).pack(side="left")

        # Action buttons
        action_frame = ttk.Frame(scan_frame)
        action_frame.pack(fill="x", pady=(0, 10))

        self.scan_btn = ttk.Button(action_frame, text="Start Scan", command=self._start_scan)
        self.scan_btn.pack(side="left")

        self.apply_btn = ttk.Button(
            action_frame,
            text="Apply Selected Renames",
            command=self._apply_renames,
            state="disabled"
        )
        self.apply_btn.pack(side="left", padx=(10, 0))

        ttk.Checkbutton(
            action_frame,
            text="Include Low Confidence",
            variable=self.include_low_var
        ).pack(side="left", padx=(10, 0))

        ttk.Button(action_frame, text="Clear Results", command=self._clear_results).pack(side="right")

        # Selection controls
        selection_frame = ttk.Frame(scan_frame)
        selection_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(selection_frame, text="Selection:").pack(side="left", padx=(0, 5))
        ttk.Button(selection_frame, text="Select All", command=self._select_all).pack(side="left", padx=2)
        ttk.Button(selection_frame, text="Deselect All", command=self._deselect_all).pack(side="left", padx=2)
        ttk.Button(selection_frame, text="High Confidence Only", command=self._select_high_confidence).pack(side="left", padx=2)

        self.selection_label = ttk.Label(selection_frame, text="Selected: 0 / 0")
        self.selection_label.pack(side="right", padx=10)

        # Results tree
        results_frame = ttk.LabelFrame(scan_frame, text="Proposed Changes", padding="10")
        results_frame.pack(fill="both", expand=True)

        columns = ("selected", "original", "new_name", "type", "confidence")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", selectmode="extended")

        self.results_tree.heading("selected", text="Sel", command=self._toggle_all_selection)
        self.results_tree.heading("original", text="Original Name")
        self.results_tree.heading("new_name", text="New Name")
        self.results_tree.heading("type", text="Type")
        self.results_tree.heading("confidence", text="Confidence")

        self.results_tree.column("selected", width=40, anchor="center")
        self.results_tree.column("original", width=350)
        self.results_tree.column("new_name", width=350)
        self.results_tree.column("type", width=80)
        self.results_tree.column("confidence", width=80)

        self.results_tree.bind("<Double-Button-1>", self._on_item_double_click)
        self.results_tree.bind("<Button-3>", self._show_context_menu)  # Right-click

        # Context menu
        self.context_menu = tk.Menu(self.results_tree, tearoff=0)
        self.context_menu.add_command(label="View/Edit Metadata", command=self._view_metadata)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Selection", command=self._toggle_selected_item)
        self.context_menu.add_command(label="Edit New Name", command=self._edit_new_name)

        y_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        x_scroll = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

    def _create_history_tab(self):
        """Create the history/rollback tab."""
        history_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(history_frame, text="History")

        btn_frame = ttk.Frame(history_frame)
        btn_frame.pack(fill="x", pady=(0, 10))

        ttk.Button(btn_frame, text="Refresh List", command=self._refresh_history).pack(side="left")
        self.rollback_btn = ttk.Button(
            btn_frame,
            text="Rollback Selected",
            command=self._rollback_selected,
            state="disabled"
        )
        self.rollback_btn.pack(side="left", padx=(10, 0))

        columns = ("id", "timestamp", "path", "operations", "status")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings", selectmode="browse")

        self.history_tree.heading("id", text="ID")
        self.history_tree.heading("timestamp", text="Timestamp")
        self.history_tree.heading("path", text="Root Path")
        self.history_tree.heading("operations", text="Ops")
        self.history_tree.heading("status", text="Status")

        self.history_tree.column("id", width=150)
        self.history_tree.column("timestamp", width=150)
        self.history_tree.column("path", width=400)
        self.history_tree.column("operations", width=80)
        self.history_tree.column("status", width=100)

        y_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=y_scroll.set)

        self.history_tree.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

        self.history_tree.bind("<<TreeviewSelect>>", self._on_history_select)

    def _create_settings_tab(self):
        """Create the settings tab."""
        settings_frame = ttk.Frame(self.notebook, padding="15")
        self.notebook.add(settings_frame, text="Settings")

        # LLM Provider Configuration
        api_frame = ttk.LabelFrame(settings_frame, text="LLM Provider Configuration", padding="10")
        api_frame.pack(fill="x", pady=(0, 10))

        grid = ttk.Frame(api_frame)
        grid.pack(fill="x")

        # Provider selection
        ttk.Label(grid, text="Provider:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(
            grid,
            textvariable=self.provider_var,
            values=["OpenAI", "Anthropic (Claude)", "Google (Gemini)", "OpenRouter"],
            state="readonly",
            width=20
        )
        self.provider_combo.grid(row=0, column=1, sticky="w")
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        # API Key
        ttk.Label(grid, text="API Key:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0))
        self.api_entry = ttk.Entry(grid, textvariable=self.api_key_var, width=50, show="*")
        self.api_entry.grid(row=1, column=1, sticky="w", pady=(10, 0))

        btn_frame = ttk.Frame(grid)
        btn_frame.grid(row=1, column=2, padx=(10, 0), pady=(10, 0))
        ttk.Button(btn_frame, text="Show", width=6, command=self._toggle_api_key).pack(side="left")
        ttk.Button(btn_frame, text="Save", command=self._save_api_key).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Test", command=self._test_api_connection).pack(side="left")

        # Model selection
        ttk.Label(grid, text="Model:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            grid,
            textvariable=self.model_var,
            state="readonly",
            width=40
        )
        self.model_combo.grid(row=2, column=1, sticky="w", pady=(10, 0))

        # Refresh models button
        refresh_btn = ttk.Button(grid, text="Refresh Models", command=self._refresh_models)
        refresh_btn.grid(row=2, column=2, padx=(10, 0), pady=(10, 0))

        # Provider info label
        self.provider_info = ttk.Label(grid, text="", font=("Segoe UI", 9), foreground="gray")
        self.provider_info.grid(row=3, column=1, sticky="w", pady=(5, 0))

        # General Settings
        gen_frame = ttk.LabelFrame(settings_frame, text="General Settings", padding="10")
        gen_frame.pack(fill="x", pady=(0, 10))

        self.restructure_var = tk.BooleanVar()
        ttk.Checkbutton(
            gen_frame,
            text="Restructure Folders (Move files to proper folder structure)",
            variable=self.restructure_var
        ).pack(anchor="w")

        perf_grid = ttk.Frame(gen_frame)
        perf_grid.pack(fill="x", pady=(10, 0))

        ttk.Label(perf_grid, text="Confidence Threshold (%):").pack(side="left")
        self.conf_var = tk.IntVar()
        ttk.Spinbox(perf_grid, from_=0, to=100, textvariable=self.conf_var, width=5).pack(side="left", padx=5)

        ttk.Label(perf_grid, text="Batch Size:").pack(side="left", padx=(20, 0))
        self.batch_var = tk.IntVar()
        ttk.Spinbox(perf_grid, from_=5, to=50, textvariable=self.batch_var, width=5).pack(side="left", padx=5)

        ttk.Button(gen_frame, text="Save Settings", command=self._save_general_settings).pack(anchor="e", pady=10)

        # Config location info
        info_frame = ttk.LabelFrame(settings_frame, text="Configuration", padding="10")
        info_frame.pack(fill="x", pady=(0, 10))

        config_dir = get_config_dir()
        ttk.Label(
            info_frame,
            text=f"Config stored in: {config_dir}",
            font=("Consolas", 9)
        ).pack(anchor="w")

        ttk.Button(
            info_frame,
            text="Open Config Folder",
            command=lambda: os.startfile(config_dir)
        ).pack(anchor="w", pady=(5, 0))

    def _on_provider_change(self, event=None):
        """Handle provider change - update model list and API key."""
        provider_display = self.provider_var.get()
        provider_map = {
            "OpenAI": "openai",
            "Anthropic (Claude)": "anthropic",
            "Google (Gemini)": "google",
            "OpenRouter": "openrouter"
        }
        provider = provider_map.get(provider_display, "openai")

        # Update config
        config = load_config()
        config["llm_provider"] = provider
        save_config(config)

        # Update model dropdown
        models = get_available_models(provider)
        model_values = [f"{m[0]} - {m[1]}" for m in models]
        self.model_combo['values'] = model_values

        # Set current model
        current_model = config.get(f"{provider}_model", models[0][0] if models else "")
        for i, m in enumerate(models):
            if m[0] == current_model:
                self.model_combo.current(i)
                break
        else:
            if model_values:
                self.model_combo.current(0)

        # Update API key display
        self.api_key_var.set(get_api_key(provider))

        # Update info label
        info_text = {
            "openai": "Get key from platform.openai.com",
            "anthropic": "Get key from console.anthropic.com",
            "google": "Get key from aistudio.google.com",
            "openrouter": "Get key from openrouter.ai - Use any model!"
        }
        self.provider_info.config(text=info_text.get(provider, ""))

    def _refresh_models(self):
        """Refresh available models from the API."""
        provider_display = self.provider_var.get()
        provider_map = {
            "OpenAI": "openai",
            "Anthropic (Claude)": "anthropic",
            "Google (Gemini)": "google",
            "OpenRouter": "openrouter"
        }
        provider = provider_map.get(provider_display, "openai")

        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key first to fetch models.")
            return

        self.progress_panel.update_progress(50, "Fetching models...", f"Connecting to {provider_display} API...")

        def fetch_thread():
            try:
                clear_model_cache()
                models = fetch_available_models(provider, api_key)
                if models:
                    self.msg_queue.put(("update_models", (provider, models)))
                    self.msg_queue.put(("status", ("Ready", 0, f"Fetched {len(models)} models")))
                else:
                    self.msg_queue.put(("status", ("Ready", 0, "Using default model list")))
            except Exception as e:
                self.msg_queue.put(("status", ("Error", 0, f"Failed to fetch models: {e}")))

        threading.Thread(target=fetch_thread, daemon=True).start()

    def _update_models_ui(self, provider, models):
        """Update the model dropdown with fetched models."""
        model_values = [f"{m[0]} - {m[1]}" for m in models]
        self.model_combo['values'] = model_values
        if model_values:
            self.model_combo.current(0)

    def _load_config(self):
        """Load configuration into UI."""
        try:
            config = load_config()
            self.smart_filter_var.set(config.get("smart_folder_filter", True))
            self.restructure_var.set(config.get("restructure_folders", True))
            self.conf_var.set(config.get("confidence_threshold", 80))
            self.batch_var.set(config.get("gpt_batch_size", 25))

            # LLM Provider
            provider = config.get("llm_provider", "openai")
            provider_map = {
                "openai": "OpenAI",
                "anthropic": "Anthropic (Claude)",
                "google": "Google (Gemini)",
                "openrouter": "OpenRouter"
            }
            self.provider_var.set(provider_map.get(provider, "OpenAI"))
            self._on_provider_change()  # This updates model list and API key

            # Platform
            platform = config.get("platform", PLATFORM_GENERIC)
            platform_map = {
                PLATFORM_GENERIC: "Generic",
                PLATFORM_PLEX: "Plex",
                PLATFORM_JELLYFIN: "Jellyfin",
                PLATFORM_EMBY: "Emby"
            }
            self.platform_var.set(platform_map.get(platform, "Generic"))
            self._update_plex_options_visibility()

            # Mode
            self.mode_var.set(config.get("mode", "media"))
            self._on_mode_change()

            # Custom prompt indicator
            if config.get("custom_prompt_enabled") and config.get("custom_prompt"):
                self.custom_prompt_indicator.config(text="[Custom prompt active]")
                self.custom_prompt_enabled.set(True)
            else:
                self.custom_prompt_indicator.config(text="")
                self.custom_prompt_enabled.set(False)

            # Recent paths
            recent = get_recent_paths()
            self.path_combo['values'] = recent
            if recent:
                self.path_combo.set(recent[0])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def _on_mode_change(self):
        """Handle mode change between media and mass."""
        mode = self.mode_var.get()
        if mode == "media":
            self.platform_frame.pack(side="left", padx=20)
            self._update_plex_options_visibility()
        else:
            self.platform_frame.pack_forget()

    def _on_platform_change(self, event=None):
        """Handle platform change."""
        platform = self.platform_var.get()
        platform_map = {
            "Generic": PLATFORM_GENERIC,
            "Plex": PLATFORM_PLEX,
            "Jellyfin": PLATFORM_JELLYFIN,
            "Emby": PLATFORM_EMBY
        }
        set_platform(platform_map.get(platform, PLATFORM_GENERIC))
        self._update_plex_options_visibility()

    def _update_plex_options_visibility(self):
        """Show/hide Plex options button."""
        if self.platform_var.get() == "Plex":
            self.plex_options_btn.pack(side="left", padx=5)
        else:
            self.plex_options_btn.pack_forget()

    def _show_plex_options(self):
        """Show Plex options dialog."""
        config = load_config()
        dialog = PlexOptionsDialog(
            self.root,
            config.get("plex_agent", ""),
            config.get("plex_scanner", ""),
            config.get("plex_options_enabled", False)
        )
        self.root.wait_window(dialog)

        if dialog.result:
            agent, scanner, enabled = dialog.result
            config = load_config()
            config["plex_agent"] = agent
            config["plex_scanner"] = scanner
            config["plex_options_enabled"] = enabled
            save_config(config)
            status = "enabled" if enabled else "disabled"
            messagebox.showinfo("Saved", f"Plex options saved ({status}).")

    def _show_custom_prompt(self):
        """Show custom prompt dialog."""
        config = load_config()
        current = config.get("custom_prompt", "")

        dialog = CustomPromptDialog(self.root, current)
        self.root.wait_window(dialog)

        if dialog.result:
            action, prompt = dialog.result
            if action == "save":
                set_custom_prompt(prompt, True)
                self.custom_prompt_indicator.config(text="[Custom prompt active]")
                self.custom_prompt_enabled.set(True)
            elif action == "clear":
                set_custom_prompt("", False)
                self.custom_prompt_indicator.config(text="")
                self.custom_prompt_enabled.set(False)

    def _browse_directory(self):
        path = filedialog.askdirectory()
        if path:
            self.current_path.set(path)

    def _toggle_api_key(self):
        current = self.api_entry.cget("show")
        self.api_entry.config(show="" if current else "*")

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        if key:
            # Get current provider
            provider_display = self.provider_var.get()
            provider_map = {
                "OpenAI": "openai",
                "Anthropic (Claude)": "anthropic",
                "Google (Gemini)": "google",
                "OpenRouter": "openrouter"
            }
            provider = provider_map.get(provider_display, "openai")
            set_api_key(key, provider)
            messagebox.showinfo("Success", f"API Key Saved for {provider_display}")

    def _save_general_settings(self):
        try:
            config = load_config()

            # Get current provider and model
            provider_display = self.provider_var.get()
            provider_map = {
                "OpenAI": "openai",
                "Anthropic (Claude)": "anthropic",
                "Google (Gemini)": "google",
                "OpenRouter": "openrouter"
            }
            provider = provider_map.get(provider_display, "openai")

            # Extract model ID from display string (format: "model_id - description")
            model_display = self.model_var.get()
            model_id = model_display.split(" - ")[0] if " - " in model_display else model_display

            config["llm_provider"] = provider
            config[f"{provider}_model"] = model_id
            config["restructure_folders"] = self.restructure_var.get()
            config["confidence_threshold"] = self.conf_var.get()
            config["gpt_batch_size"] = self.batch_var.get()
            config["smart_folder_filter"] = self.smart_filter_var.get()
            config["mode"] = self.mode_var.get()
            save_config(config)
            messagebox.showinfo("Success", "Settings Saved")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _test_api_connection(self):
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("Warning", "Please enter an API key first.")
            return

        # Get current provider
        provider_display = self.provider_var.get()
        provider_map = {
            "OpenAI": "openai",
            "Anthropic (Claude)": "anthropic",
            "Google (Gemini)": "google",
            "OpenRouter": "openrouter"
        }
        provider = provider_map.get(provider_display, "openai")

        self.progress_panel.update_progress(0, "Testing API...", f"Connecting to {provider_display}...")
        threading.Thread(target=self._test_api_thread, args=(key, provider), daemon=True).start()

    def _test_api_thread(self, key, provider):
        try:
            if provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=key)
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1
                )
            elif provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=key)
                client.messages.create(
                    model="claude-haiku-4-20250514",
                    max_tokens=1,
                    messages=[{"role": "user", "content": "hi"}]
                )
            elif provider == "google":
                import google.generativeai as genai
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                model.generate_content("hi", generation_config=genai.types.GenerationConfig(max_output_tokens=1))
            elif provider == "openrouter":
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
                client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1
                )

            self.msg_queue.put(("status", ("Ready", 0, "API Test Passed!")))
            self.root.after(0, lambda: messagebox.showinfo("Success", "API Connection Successful!"))
        except Exception as e:
            self.msg_queue.put(("status", ("Error", 0, "API Test Failed")))
            self.root.after(0, lambda: messagebox.showerror("Error", f"API Connection Failed:\n{str(e)}"))

    def _clear_results(self):
        self.results_tree.delete(*self.results_tree.get_children())
        self.current_plan = None
        self.selection_state = {}
        self.apply_btn.config(state="disabled")
        self.selection_label.config(text="Selected: 0 / 0")
        self.progress_panel.update_progress(0, "Ready", "")

    # Selection management
    def _on_item_double_click(self, event):
        item = self.results_tree.identify_row(event.y)
        if item:
            self._toggle_item_selection(item)

    def _show_context_menu(self, event):
        """Show context menu on right-click."""
        item = self.results_tree.identify_row(event.y)
        if item:
            self.results_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _view_metadata(self):
        """View/edit metadata for selected file."""
        sel = self.results_tree.selection()
        if not sel:
            return

        values = self.results_tree.item(sel[0], "values")
        original_name = values[1]

        # Find the full path from the plan
        file_path = None
        if self.current_plan:
            for op in self.current_plan.manifest.operations:
                if Path(op["original_path"]).name == original_name:
                    file_path = op["original_path"]
                    break

        if file_path:
            dialog = MetadataDialog(self.root, file_path)
            self.root.wait_window(dialog)
        else:
            messagebox.showwarning("Warning", "Could not find file path.")

    def _toggle_selected_item(self):
        """Toggle selection for context menu item."""
        sel = self.results_tree.selection()
        if sel:
            self._toggle_item_selection(sel[0])

    def _edit_new_name(self):
        """Edit the new name for selected item."""
        sel = self.results_tree.selection()
        if not sel:
            return

        values = list(self.results_tree.item(sel[0], "values"))
        current_name = values[2]

        # Simple dialog to edit name
        new_name = tk.simpledialog.askstring(
            "Edit Name",
            "Enter new file name:",
            initialvalue=current_name,
            parent=self.root
        )

        if new_name and new_name != current_name:
            values[2] = new_name
            self.results_tree.item(sel[0], values=values)

            # Update the plan
            original_name = values[1]
            if self.current_plan:
                for op in self.current_plan.manifest.operations:
                    if Path(op["original_path"]).name == original_name:
                        # Keep extension from new path
                        old_ext = Path(op["new_path"]).suffix
                        new_ext = Path(new_name).suffix
                        if not new_ext:
                            new_name += old_ext
                        op["new_path"] = str(Path(op["new_path"]).parent / new_name)
                        break

    def _toggle_item_selection(self, item_id):
        current = self.selection_state.get(item_id, True)
        self.selection_state[item_id] = not current
        self._update_tree_item_display(item_id)
        self._update_selection_count()

    def _toggle_all_selection(self):
        all_items = self.results_tree.get_children()
        if not all_items:
            return
        all_selected = all(self.selection_state.get(item, True) for item in all_items)
        new_state = not all_selected
        for item in all_items:
            self.selection_state[item] = new_state
            self._update_tree_item_display(item)
        self._update_selection_count()

    def _select_all(self):
        for item in self.results_tree.get_children():
            self.selection_state[item] = True
            self._update_tree_item_display(item)
        self._update_selection_count()

    def _deselect_all(self):
        for item in self.results_tree.get_children():
            self.selection_state[item] = False
            self._update_tree_item_display(item)
        self._update_selection_count()

    def _select_high_confidence(self):
        for item in self.results_tree.get_children():
            tags = self.results_tree.item(item, "tags")
            is_high = "high" in tags
            self.selection_state[item] = is_high
            self._update_tree_item_display(item)
        self._update_selection_count()

    def _update_tree_item_display(self, item_id):
        is_selected = self.selection_state.get(item_id, True)
        values = list(self.results_tree.item(item_id, "values"))
        values[0] = "Y" if is_selected else "N"
        self.results_tree.item(item_id, values=values)

    def _update_selection_count(self):
        all_items = self.results_tree.get_children()
        selected = sum(1 for item in all_items if self.selection_state.get(item, True))
        self.selection_label.config(text=f"Selected: {selected} / {len(all_items)}")

    # Scanning
    def _start_scan(self):
        path = self.current_path.get().strip()
        if not os.path.isdir(path):
            messagebox.showerror("Error", "Invalid Directory")
            return

        if self.is_processing:
            return
        self.is_processing = True
        self.scan_btn.config(state="disabled")
        self._clear_results()

        add_recent_path(path)
        self.path_combo['values'] = get_recent_paths()

        threading.Thread(target=self._scan_thread, args=(path,), daemon=True).start()

    def _scan_thread(self, path):
        try:
            config = load_config()
            custom_prompt = get_custom_prompt() if self.custom_prompt_enabled.get() else None

            # Scan
            self.msg_queue.put(("status", ("Scanning...", 10, "Finding files...")))

            def scan_cb(p: ScanProgress):
                details = f"Found {p.files_found} files in {p.folders_scanned} folders"
                self.msg_queue.put(("status", ("Scanning...", 10, details)))

            media_files = scan_directory(path, config, progress_callback=scan_cb)

            if not media_files:
                mode = config.get("mode", "media")
                if mode == "mass":
                    msg = ("No files found in the selected directory.\n\n"
                           "Possible reasons:\n"
                           "- Directory is empty or all files are hidden\n"
                           "- All files are in excluded folders\n"
                           "- Check your extension filter settings")
                else:
                    msg = ("No media files found in the selected directory.\n\n"
                           "Possible reasons:\n"
                           "- Directory doesn't contain supported video files\n"
                           "- All files are in excluded folders\n"
                           "- Check your video extension settings\n"
                           "- Try switching to 'Mass Rename' mode for all file types")
                self.msg_queue.put(("status", ("Complete", 100, "No files found in directory")))
                self.msg_queue.put(("info", msg))
                self.msg_queue.put(("done", None))
                return

            # Identify
            self.msg_queue.put(("status", ("Identifying...", 20, f"Identifying {len(media_files)} files...")))

            def gpt_cb(p: GPTProgress):
                pct = 20 + (p.files_processed / p.total_files * 70)
                eta = f"{p.estimated_remaining:.0f}s" if p.estimated_remaining else "?"
                details = f"Processed {p.files_processed}/{p.total_files} | ETA: {eta}"
                self.msg_queue.put(("status", ("Identifying...", pct, details)))

            filenames_with_paths = [(f.filename, str(f.path)) for f in media_files]
            media_info = identify_all_media(
                filenames_with_paths,
                config,
                progress_callback=gpt_cb,
                custom_prompt=custom_prompt
            )

            # Generate plan
            self.msg_queue.put(("status", ("Planning...", 95, "Generating rename plan...")))
            plan = generate_rename_plan(media_files, media_info, path, config)

            self.msg_queue.put(("results", (plan, media_files, media_info)))
            self.msg_queue.put(("status", (
                "Complete",
                100,
                f"Plan ready: {len(plan.high_confidence) + len(plan.low_confidence)} renames"
            )))

        except Exception as e:
            self.msg_queue.put(("error", str(e)))
        finally:
            self.msg_queue.put(("done", None))

    def _apply_renames(self):
        if not self.current_plan:
            return

        selected_count = sum(
            1 for item in self.results_tree.get_children()
            if self.selection_state.get(item, True)
        )

        if selected_count == 0:
            messagebox.showwarning("No Selection", "No items selected for renaming.")
            return

        msg = f"Apply {selected_count} selected rename(s)?"
        if not messagebox.askyesno("Confirm", msg):
            return

        self.is_processing = True
        self.apply_btn.config(state="disabled")
        threading.Thread(target=self._apply_thread, daemon=True).start()

    def _apply_thread(self):
        try:
            config = load_config()
            self.msg_queue.put(("status", ("Applying...", 0, "Starting rename operations...")))

            selected_operations = []
            threshold = config.get("confidence_threshold", 80)
            include_low = self.include_low_var.get()

            for item_id in self.results_tree.get_children():
                if not self.selection_state.get(item_id, True):
                    continue

                values = self.results_tree.item(item_id, "values")
                original_name = values[1]

                for op in self.current_plan.manifest.operations:
                    if Path(op["original_path"]).name == original_name:
                        if include_low or op.get("confidence", 0) >= threshold:
                            selected_operations.append(op)
                        break

            filtered_manifest = self.current_plan.manifest
            filtered_manifest.operations = selected_operations

            success, failed, errs = execute_rename_plan(
                filtered_manifest,
                include_low_confidence=include_low,
                config=config,
                folder_renames=self.current_plan.folder_renames
            )

            msg = f"Applied: {success} success, {failed} failed"
            if failed > 0:
                msg += f". Errors: {'; '.join(errs[:3])}"

            self.msg_queue.put(("status", ("Done", 100, msg)))
            self.msg_queue.put(("refresh_history", None))

        except Exception as e:
            self.msg_queue.put(("error", str(e)))
        finally:
            self.msg_queue.put(("done", None))

    # History
    def _refresh_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        try:
            config = load_config()
            manifests = list_manifests(config)
            for m in manifests:
                st = "Rolled Back" if m.rolled_back else "Applied" if m.applied else "Pending"
                self.history_tree.insert("", "end", values=(
                    m.id, m.timestamp, m.root_path, m.total_operations, st
                ))
        except Exception:
            pass

    def _on_history_select(self, e):
        sel = self.history_tree.selection()
        if sel:
            st = self.history_tree.item(sel[0])['values'][4]
            self.rollback_btn.config(state="normal" if st == "Applied" else "disabled")

    def _rollback_selected(self):
        sel = self.history_tree.selection()
        if not sel:
            return
        mid = self.history_tree.item(sel[0])['values'][0]
        if not messagebox.askyesno("Confirm", "Rollback this operation?"):
            return

        self.is_processing = True
        threading.Thread(target=self._rollback_thread, args=(mid,), daemon=True).start()

    def _rollback_thread(self, mid):
        try:
            self.msg_queue.put(("status", ("Rolling back...", 50, f"Restoring files...")))
            config = load_config()
            manifest = load_manifest(mid, config)
            if manifest:
                s, f, e = execute_rollback(manifest, config)
                self.msg_queue.put(("status", ("Done", 100, f"Restored {s} files.")))
                self.msg_queue.put(("refresh_history", None))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))
        finally:
            self.msg_queue.put(("done", None))

    def _process_messages(self):
        try:
            while True:
                type_, data = self.msg_queue.get_nowait()

                if type_ == "status":
                    st, pct, det = data
                    self.progress_panel.update_progress(pct, st, det)
                elif type_ == "error":
                    messagebox.showerror("Error", data)
                elif type_ == "info":
                    messagebox.showinfo("Info", data)
                elif type_ == "done":
                    self.is_processing = False
                    self.scan_btn.config(state="normal")
                    # If data contains a message, show it
                    if data and isinstance(data, str):
                        messagebox.showinfo("Complete", data)
                elif type_ == "results":
                    plan, mfiles, minfo = data
                    self.current_plan = plan
                    self.media_files = mfiles
                    self.media_info = minfo
                    self._populate_results(plan)
                    if plan.high_confidence or plan.folder_renames:
                        self.apply_btn.config(state="normal")
                elif type_ == "refresh_history":
                    self._refresh_history()
                elif type_ == "update_models":
                    provider, models = data
                    self._update_models_ui(provider, models)

        except queue.Empty:
            pass
        self.root.after(100, self._process_messages)

    def _populate_results(self, plan):
        self.results_tree.delete(*self.results_tree.get_children())
        self.selection_state = {}

        for r in plan.high_confidence:
            item_id = self.results_tree.insert("", "end", values=(
                "Y",
                Path(r['original_path']).name,
                Path(r['new_path']).name,
                r.get('media_type', '?'),
                f"{r.get('confidence', 0)}%"
            ), tags=("high",))
            self.selection_state[item_id] = True

        for r in plan.low_confidence:
            item_id = self.results_tree.insert("", "end", values=(
                "Y",
                Path(r['original_path']).name,
                Path(r['new_path']).name,
                r.get('media_type', '?'),
                f"{r.get('confidence', 0)}%"
            ), tags=("low",))
            self.selection_state[item_id] = True

        if plan.folder_renames:
            for r in plan.folder_renames:
                item_id = self.results_tree.insert("", "end", values=(
                    "Y",
                    r.get('original_name', '?'),
                    r.get('new_name', '?'),
                    "Folder",
                    "-"
                ), tags=("folder",))
                self.selection_state[item_id] = True

        self.results_tree.tag_configure("high", foreground="green")
        self.results_tree.tag_configure("low", foreground="orange")
        self.results_tree.tag_configure("folder", foreground="blue")

        self._update_selection_count()


def main():
    root = tk.Tk()

    style = ttk.Style()
    if 'vista' in style.theme_names():
        style.theme_use('vista')

    app = RenameifyGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
