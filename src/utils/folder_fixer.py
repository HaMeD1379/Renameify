"""
Folder fixer module - fixes incorrectly named/structured media folders.

Handles cases like:
- "South Park [1997-]Season 26" -> "South Park [1997-]/Season 26/"
- Moves files from merged folders to proper structure
"""
import os
import re
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.config import load_config


@dataclass
class FolderFix:
    """Represents a folder fix operation."""
    original_path: str
    new_parent_path: str
    new_season_path: str
    series_name: str
    year_range: str
    season_num: int
    files_to_move: List[str]
    fix_type: str  # "split_merged", "rename_only", "restructure", "rename_season"


# Pattern to detect merged folders like "South Park [1997-]Season 26"
MERGED_FOLDER_PATTERN = re.compile(
    r'^(.+?)\s*\[(\d{4})-(\d{0,4})\](Season\s*(\d{1,2}))$',
    re.IGNORECASE
)

# Pattern to detect series folders with year
SERIES_FOLDER_PATTERN = re.compile(
    r'^(.+?)\s*\[(\d{4})-(\d{0,4})\]$'
)

# Pattern to detect season folders that need renaming (S01, S02, Season 1, etc)
# These should become "Season 01", "Season 02", etc.
BAD_SEASON_FOLDER_PATTERN = re.compile(
    r'^S(\d{1,2})$',  # S01, S1, S02, etc.
    re.IGNORECASE
)

# Correct season folder pattern
CORRECT_SEASON_FOLDER_PATTERN = re.compile(
    r'^Season\s+(\d{2})$',  # Season 01, Season 02 (with zero padding)
    re.IGNORECASE
)


def scan_for_folder_issues(
    root_path: str,
    config: Optional[dict] = None,
    progress_callback: Optional[callable] = None
) -> List[FolderFix]:
    """
    Scan for folders that need fixing.

    Args:
        root_path: Root directory to scan
        config: Optional config dict
        progress_callback: Optional progress callback

    Returns:
        List of FolderFix objects describing fixes needed
    """
    if config is None:
        config = load_config()

    root = Path(root_path)
    fixes_needed = []
    folders_scanned = 0

    try:
        for item in root.iterdir():
            if not item.is_dir():
                continue

            folders_scanned += 1
            if progress_callback and folders_scanned % 10 == 0:
                progress_callback(f"Scanning folders... {folders_scanned}")

            folder_name = item.name

            # Check for merged folder pattern: "Show [Year-]Season XX"
            match = MERGED_FOLDER_PATTERN.match(folder_name)
            if match:
                series_name = match.group(1).strip()
                year_start = match.group(2)
                year_end = match.group(3) or ""
                season_part = match.group(4)
                season_num = int(match.group(5))

                year_range = f"{year_start}-{year_end}" if year_end else f"{year_start}-"

                # Build correct paths
                correct_series_folder = f"{series_name} [{year_range}]"
                correct_season_folder = f"Season {season_num:02d}"

                new_parent = root / correct_series_folder
                new_season = new_parent / correct_season_folder

                # Get files in the merged folder
                files_to_move = []
                for file_item in item.rglob("*"):
                    if file_item.is_file():
                        files_to_move.append(str(file_item))

                fixes_needed.append(FolderFix(
                    original_path=str(item),
                    new_parent_path=str(new_parent),
                    new_season_path=str(new_season),
                    series_name=series_name,
                    year_range=year_range,
                    season_num=season_num,
                    files_to_move=files_to_move,
                    fix_type="split_merged"
                ))

            # Check if this is a series folder with season subfolders that need fixing
            else:
                series_match = SERIES_FOLDER_PATTERN.match(folder_name)
                if series_match:
                    series_name = series_match.group(1).strip()
                    year_start = series_match.group(2)
                    year_end = series_match.group(3) or ""
                    year_range = f"{year_start}-{year_end}" if year_end else f"{year_start}-"

                    # Check subfolders for bad season names (S01 -> Season 01)
                    for subfolder in item.iterdir():
                        if subfolder.is_dir():
                            # Check for merged pattern first
                            sub_match = MERGED_FOLDER_PATTERN.match(subfolder.name)
                            if sub_match:
                                # Subfolder is merged - fix it
                                season_num = int(sub_match.group(5))

                                year_range = f"{year_start}-{year_end}" if year_end else f"{year_start}-"

                                correct_season_folder = f"Season {season_num:02d}"
                                new_season = item / correct_season_folder

                                files_to_move = []
                                for file_item in subfolder.rglob("*"):
                                    if file_item.is_file():
                                        files_to_move.append(str(file_item))

                                fixes_needed.append(FolderFix(
                                    original_path=str(subfolder),
                                    new_parent_path=str(item),
                                    new_season_path=str(new_season),
                                    series_name=series_name,
                                    year_range=year_range,
                                    season_num=season_num,
                                    files_to_move=files_to_move,
                                    fix_type="fix_subfolder"
                                ))

                            # Check for bad season folder names like S01, S02
                            else:
                                bad_season_match = BAD_SEASON_FOLDER_PATTERN.match(subfolder.name)
                                if bad_season_match:
                                    season_num = int(bad_season_match.group(1))
                                    correct_season_folder = f"Season {season_num:02d}"
                                    new_season = item / correct_season_folder

                                    # Only add if the name is actually different
                                    if subfolder.name != correct_season_folder:
                                        files_to_move = []
                                        for file_item in subfolder.rglob("*"):
                                            if file_item.is_file():
                                                files_to_move.append(str(file_item))

                                        fixes_needed.append(FolderFix(
                                            original_path=str(subfolder),
                                            new_parent_path=str(item),
                                            new_season_path=str(new_season),
                                            series_name=series_name,
                                            year_range=year_range,
                                            season_num=season_num,
                                            files_to_move=files_to_move,
                                            fix_type="rename_season"
                                        ))

    except PermissionError as e:
        if progress_callback:
            progress_callback(f"Permission error: {e}")
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error: {e}")

    return fixes_needed


def format_folder_fixes(fixes: List[FolderFix]) -> str:
    """Format folder fixes for display."""
    if not fixes:
        return "\n  ✓ No folder structure issues found!\n"

    lines = [
        "",
        "=" * 80,
        "  FOLDER STRUCTURE ISSUES FOUND",
        "=" * 80,
        f"\n  Found {len(fixes)} folders that need fixing:\n"
    ]

    for i, fix in enumerate(fixes, 1):
        fix_type_display = {
            "split_merged": "SPLIT MERGED",
            "fix_subfolder": "FIX SUBFOLDER",
            "rename_season": "RENAME SEASON",
            "restructure": "RESTRUCTURE"
        }.get(fix.fix_type, fix.fix_type.upper())

        lines.append(f"  [{i}] {fix_type_display}: {fix.series_name}")
        lines.append(f"      Current:  {Path(fix.original_path).name}")

        if fix.fix_type == "rename_season":
            lines.append(f"      Rename to: {Path(fix.new_season_path).name}")
        else:
            lines.append(f"      Fixed:    {Path(fix.new_parent_path).name}/")
            lines.append(f"                └── {Path(fix.new_season_path).name}/")

        lines.append(f"      Files:    {len(fix.files_to_move)} files")
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


def save_folder_fix_plan(fixes: List[FolderFix], root_path: str) -> str:
    """Save folder fix plan to a text file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_filename = f"folder_fix_plan_{timestamp}.txt"

    app_dir = Path(__file__).parent
    plan_path = app_dir / plan_filename

    lines = [
        "=" * 80,
        "  FOLDER FIX PLAN - REVIEW BEFORE APPLYING",
        "=" * 80,
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Root Path: {root_path}",
        f"Total fixes: {len(fixes)}",
        "",
        "-" * 80,
    ]

    for i, fix in enumerate(fixes, 1):
        lines.append("")
        lines.append(f"[{i}] {fix.series_name} - Season {fix.season_num:02d}")
        lines.append(f"    Type: {fix.fix_type}")
        lines.append(f"    ")
        lines.append(f"    CURRENT FOLDER:")
        lines.append(f"      {fix.original_path}")
        lines.append(f"    ")
        lines.append(f"    WILL BECOME:")
        lines.append(f"      {fix.new_parent_path}/")
        lines.append(f"      └── Season {fix.season_num:02d}/")
        lines.append(f"    ")
        lines.append(f"    FILES TO MOVE ({len(fix.files_to_move)}):")
        for file_path in fix.files_to_move[:10]:
            lines.append(f"      - {Path(file_path).name}")
        if len(fix.files_to_move) > 10:
            lines.append(f"      ... and {len(fix.files_to_move) - 10} more")
        lines.append("")
        lines.append("-" * 80)

    lines.append("")
    lines.append("END OF PLAN")

    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(plan_path)


def execute_folder_fixes(
    fixes: List[FolderFix],
    config: Optional[dict] = None,
    progress_callback: Optional[callable] = None
) -> Tuple[int, int, List[str]]:
    """
    Execute folder fix operations.

    Args:
        fixes: List of FolderFix objects
        config: Optional config dict
        progress_callback: Optional progress callback

    Returns:
        Tuple of (successful, failed, errors)
    """
    if config is None:
        config = load_config()

    successful = 0
    failed = 0
    errors = []

    for i, fix in enumerate(fixes, 1):
        if progress_callback:
            progress_callback(f"Fixing {i}/{len(fixes)}: {fix.series_name} Season {fix.season_num}")

        try:
            original_path = Path(fix.original_path)
            new_parent = Path(fix.new_parent_path)
            new_season = Path(fix.new_season_path)

            # For simple season folder renames (S01 -> Season 01), just rename the folder
            if fix.fix_type == "rename_season" and original_path.parent == new_season.parent:
                # Simple rename - just rename the folder directly
                if not new_season.exists():
                    original_path.rename(new_season)
                    successful += 1
                else:
                    # Target exists - need to merge
                    for file_path in fix.files_to_move:
                        src = Path(file_path)
                        if src.exists():
                            dst = new_season / src.name
                            if not dst.exists():
                                shutil.move(str(src), str(dst))
                    # Remove original if empty
                    if original_path.exists() and not any(original_path.iterdir()):
                        original_path.rmdir()
                    successful += 1
                continue

            # Create the new folder structure
            new_season.mkdir(parents=True, exist_ok=True)

            # Move all files from original to new season folder
            moved_count = 0
            for file_path in fix.files_to_move:
                src = Path(file_path)
                if src.exists():
                    # Calculate relative path within original folder
                    try:
                        rel_path = src.relative_to(original_path)
                        dst = new_season / rel_path
                    except ValueError:
                        # File is not under original_path, just use filename
                        dst = new_season / src.name

                    # Create parent dirs if needed
                    dst.parent.mkdir(parents=True, exist_ok=True)

                    # Move file
                    if not dst.exists():
                        shutil.move(str(src), str(dst))
                        moved_count += 1
                    else:
                        # Handle duplicate
                        base = dst.stem
                        ext = dst.suffix
                        counter = 1
                        while dst.exists():
                            dst = dst.parent / f"{base} ({counter}){ext}"
                            counter += 1
                        shutil.move(str(src), str(dst))
                        moved_count += 1

            # Try to remove the original folder if it's empty
            try:
                if original_path.exists():
                    # Remove empty subdirectories first
                    for dirpath, dirnames, filenames in os.walk(str(original_path), topdown=False):
                        if not filenames and not dirnames:
                            os.rmdir(dirpath)

                    # Remove the main folder if empty
                    if original_path.exists() and not any(original_path.iterdir()):
                        original_path.rmdir()
            except Exception as e:
                errors.append(f"Warning: Could not remove empty folder {original_path.name}: {e}")

            successful += 1

        except Exception as e:
            failed += 1
            errors.append(f"Failed to fix {fix.series_name} Season {fix.season_num}: {e}")

    return successful, failed, errors

