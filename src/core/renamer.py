"""
Renamer module - handles generating rename plans and executing renames.
"""
import os
import shutil
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .config import load_config
from .scanner import MediaFile
from .gpt_service import MediaInfo, format_media_info, format_folder_structure
from .rollback import (
    RenameManifest, create_manifest_from_plan, save_manifest,
    load_manifest, update_manifest_status
)


# Patterns that indicate a file/folder is already properly named
PROPER_NAME_PATTERNS = [
    # Movies: Title [Year] - must have actual title (3+ chars) before year
    r'^.{3,}\s*\[\d{4}\]$',
    # Series folder: Title [Year-Year] or Title [Year-] - must have actual title
    r'^.{3,}\s*\[\d{4}-\d{0,4}\]$',
    # Season folder: Season XX (with or without leading zeros)
    r'^Season\s*\d{1,2}$',
    # Episode file: Series SxxExx - Title (must have real title, not just "Episode")
    # This pattern requires the title part to NOT be just "Episode" or "Episode X"
    r'^.{3,}\s+S\d{2}E\d{2}\s+-\s+(?!Episode(\s+\d+)?$).+$',
    # NOTE: Files like "Show S01E01" (without title) should be processed to get episode title
    # So we intentionally do NOT include a pattern for "SxxExx without title"
]

# Patterns that indicate a file NEEDS to be renamed (bad names)
BAD_NAME_PATTERNS = [
    # Just numbers like 01.mkv, 02.mkv
    r'^\d{1,3}$',
    # Generic "Episode" title (exactly "Episode")
    r'.*\s+-\s+Episode$',
    # Episode files WITHOUT a title (we want to look up the title)
    r'^.{3,}\s+S\d{2}E\d{2}$',
    # Generic numbered episode titles like "Episode 1", "Episode 2", "Episodio 1"
    r'.*\s+-\s+Episode\s+\d+$',
    r'.*\s+-\s+Episodio\s+\d+$',
    # Scene release patterns
    r'.*\b(720p|1080p|2160p|x264|x265|HEVC|BluRay|WEB-DL|HDTV)\b.*',
]

# Patterns that indicate a FOLDER is a scene-release name needing renaming
SCENE_FOLDER_PATTERNS = [
    # Scene release patterns with quality tags
    r'.*\.(720p|1080p|2160p|4K)\..*',
    r'.*\b(WEB-DL|WEBRip|BluRay|BDRip|HDTV|DVDRip|BRRip|HDRip)\b.*',
    r'.*\b(x264|x265|HEVC|H\.264|H\.265|AVC)\b.*',
    r'.*\b(DDP|DD|AAC|AC3|DTS|FLAC)\d*\.?\d*\b.*',
    r'.*\b(FLUX|RARBG|YTS|NTb|SPARKS|FGT|ETRG|YIFY)\b.*',
    r'.*-[A-Z]+\[?[a-z]*\]?$',  # Ends with -GROUP or -GROUP[tag]
    # Collection/compilation junk patterns
    r'.*\b(Complete\s*(Series|Collection|Season|Box\s*Set)?)\b.*',
    r'.*\b(The\s*Complete)\b.*',
    r'.*\b(All\s*Seasons?)\b.*',
    r'.*\b(Full\s*Series)\b.*',
    r'.*\b(Season\s*\d+\s*-\s*\d+)\b.*',  # "Season 1 - 5" style
    r'.*\b(S\d+-S\d+)\b.*',  # "S01-S05" style
    # Quality/resolution tags without dots
    r'.*\b(720p|1080p|2160p|4K|576p|480p)\b.*',
    # Source tags
    r'.*\b(Remux|REMUX)\b.*',
    # Extra info junk
    r'.*\b(Interviews?|Bonus|Extras?|Specials?|Behind.the.Scenes?)\b.*',
    r'.*\b(Documentary|Making.of)\b.*',
    # Network/channel names that shouldn't be in folder names
    r'.*\b(BBC|HBO|Netflix|Amazon|Disney\+?|Hulu|Paramount)\b.*Story.*',
]

# Junk patterns to REMOVE from folder/file names when cleaning
JUNK_PATTERNS_TO_REMOVE = [
    # Quality and source info
    r'\s*-?\s*DVDRip\s*',
    r'\s*-?\s*BDRip\s*',
    r'\s*-?\s*BluRay\s*',
    r'\s*-?\s*Blu-Ray\s*',
    r'\s*-?\s*BRRip\s*',
    r'\s*-?\s*HDRip\s*',
    r'\s*-?\s*WEB-?DL\s*',
    r'\s*-?\s*WEBRip\s*',
    r'\s*-?\s*HDTV\s*',
    r'\s*-?\s*Remux\s*',
    r'\s*-?\s*REMUX\s*',
    # Resolution
    r'\s*-?\s*\d{3,4}p\s*',  # 480p, 576p, 720p, 1080p, 2160p
    r'\s*-?\s*4K\s*',
    r'\s*-?\s*8K\s*',
    # Codecs
    r'\s*-?\s*x264\s*',
    r'\s*-?\s*x265\s*',
    r'\s*-?\s*HEVC\s*',
    r'\s*-?\s*H\.?264\s*',
    r'\s*-?\s*H\.?265\s*',
    r'\s*-?\s*AVC\s*',
    r'\s*-?\s*XviD\s*',
    # Audio
    r'\s*-?\s*DTS\s*',
    r'\s*-?\s*AC3\s*',
    r'\s*-?\s*AAC\s*',
    r'\s*-?\s*DD\d*\.?\d*\s*',
    r'\s*-?\s*DDP\d*\.?\d*\s*',
    r'\s*-?\s*Atmos\s*',
    r'\s*-?\s*TrueHD\s*',
    # Collection/compilation junk - be more aggressive
    r'\s*-?\s*The\s+Complete\s+Collection\s*',
    r'\s*-?\s*Complete\s+Collection\s*',
    r'\s*-?\s*The\s+Complete\s+Series\s*',
    r'\s*-?\s*Complete\s+Series\s*',
    r'\s*-?\s*Complete\s+Season\s*',
    r'\s*-?\s*Full\s+Series\s*',
    r'\s*-?\s*All\s+Seasons?\s*',
    r'\s*-?\s*Box\s*Set\s*',
    r'\s*-?\s*The\s+Complete\b',  # Just "The Complete" without requiring what follows
    r'\bComplete\b',  # Standalone "Complete"
    r'\s*-?\s*Collection\s*',
    # Extra content markers (more comprehensive)
    r'\s*-?\s*Interviews?\s*',
    r'\s*-?\s*Bonus\s*',
    r'\s*-?\s*Extras?\s*',
    r'\s*-?\s*Specials?\s*',
    r'\s*-?\s*Behind\s+the\s+Scenes?\s*',
    r'\s*-?\s*Documentary\s*',
    r'\s*-?\s*Making\s+of\s*',
    r'\s*-?\s*Deleted\s+Scenes?\s*',
    r'\s*-?\s*Outtakes?\s*',
    # Network/production info patterns (expanded)
    r'\s*-?\s*BBC\s+Story(\s+of\s+\d{4})?\s*',
    r'\s*-?\s*HBO\s+Story(\s+of\s+\d{4})?\s*',
    r'\s*-?\s*(BBC|HBO|Netflix|Amazon|Disney|Hulu)\s+(Original|Series|Story|Production)\s*',
    r'\bNetflix\b',  # Standalone Netflix
    # Release groups (at end)
    r'\s*-\s*[A-Z]{2,10}$',
    r'\s*\[[A-Za-z0-9]+\]$',
    # Season ranges like "S01-S05" or "Season 1-4"
    r'\s*-?\s*S\d{1,2}\s*-\s*S\d{1,2}\s*',
    r'\s*-?\s*Season\s+\d{1,2}\s*-\s*\d{1,2}\s*',
    r'\s*-?\s*Seasons?\s+\d{1,2}\s*-\s*\d{1,2}\s*',
    # Individual season markers when not in a season folder context (like "S01" in root folder name)
    r'\.S\d{1,2}\.',  # .S01. pattern
    r'\bS\d{2}\b',    # S01 as standalone word
    # Trailing dashes and junk
    r'\s*-+\s*$',
    r'\s+-\s+$',
]

# BDMV/Blu-ray structure files that should not be renamed
BDMV_MARKERS = ['index.bdmv', 'movieobject.bdmv', 'bdmv', 'certificate']
BDMV_INTERNAL_FOLDERS = ['bdmv', 'certificate', 'backup', 'playlist', 'clipinf', 'stream', 'auxdata', 'meta', 'jar']


# Folder names that are legitimate specials/extras folders, not scene-release junk
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


def _find_show_root_for_specials(file_path: Path, root_path: str) -> Optional[Path]:
    """
    Walk up from *file_path* skipping Season and Specials folders until a
    non-season, non-specials folder is found — that folder is the show root.

    Used by Plex specials consolidation to determine where ``Specials/`` should live.
    Returns ``None`` if the structure cannot be determined.
    """
    root = Path(root_path)
    current = file_path.parent
    found_season_or_specials = False

    while current.name:  # stop at filesystem root
        name_lower = current.name.lower()
        is_specials = name_lower in SPECIALS_FOLDER_NAMES
        is_season = normalize_season_folder_name(current.name) is not None

        if is_specials or is_season:
            found_season_or_specials = True
            current = current.parent
        elif found_season_or_specials:
            # We climbed through at least one season/specials folder.
            # The current folder is the show root.
            return current
        else:
            # Never hit a season/specials folder — can't determine show root
            return None

    return None


def is_scene_release_folder(folder_name: str) -> bool:
    """Check if a folder name looks like a scene-release name that needs cleanup."""
    # Don't flag legitimate specials/extras folders
    if folder_name.lower().strip() in SPECIALS_FOLDER_NAMES:
        return False

    for pattern in SCENE_FOLDER_PATTERNS:
        if re.search(pattern, folder_name, re.IGNORECASE):
            return True
    return False


def clean_folder_name(folder_name: str) -> str:
    """
    Clean a folder name by removing junk patterns (quality tags, release info, etc.)
    Returns the cleaned title portion.
    
    Example:
        "Only Fools and Horses (1981) The Complete Collection - DVDRip 576p - BBC Story of 2002 Interviews"
        -> "Only Fools and Horses (1981)"
    """
    cleaned = folder_name
    
    # Apply all junk removal patterns (multiple passes to catch chained junk)
    for _ in range(2):  # Two passes to catch patterns that become visible after first removal
        for pattern in JUNK_PATTERNS_TO_REMOVE:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # Clean up multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Clean up stray dashes and parentheses (multiple times to catch nested cases)
    for _ in range(3):
        cleaned = re.sub(r'\s*-\s*$', '', cleaned)  # Trailing dash
        cleaned = re.sub(r'^\s*-\s*', '', cleaned)  # Leading dash
        cleaned = re.sub(r'\s+-\s+', ' - ', cleaned)  # Normalize dashes
        cleaned = re.sub(r'\(\s*\)', '', cleaned)   # Empty parentheses
        cleaned = re.sub(r'\[\s*\]', '', cleaned)   # Empty brackets
        cleaned = re.sub(r'\s+', ' ', cleaned)      # Multiple spaces again
        cleaned = cleaned.strip()
        
    # Final cleanup: remove trailing punctuation and spaces
    cleaned = re.sub(r'[\s\-_\.]+$', '', cleaned)
    cleaned = re.sub(r'^[\s\-_\.]+', '', cleaned)
    
    return cleaned.strip()


def extract_title_and_year_from_folder(folder_name: str) -> tuple:
    """
    Extract clean title and year(s) from a messy folder name.
    
    Returns:
        (title, year, year_start, year_end) - year is for movies, year_start/year_end for series
    
    Examples:
        "Only Fools and Horses (1981) The Complete Collection..."
        -> ("Only Fools and Horses", None, 1981, None)
        
        "Breaking Bad [2008-2013] Complete Series..."
        -> ("Breaking Bad", None, 2008, 2013)
    """
    # First clean the folder name
    cleaned = clean_folder_name(folder_name)
    
    # Try to extract year range [YYYY-YYYY] or (YYYY-YYYY)
    year_range_match = re.search(r'[\[\(](\d{4})\s*-\s*(\d{4})?[\]\)]', cleaned)
    if year_range_match:
        title = re.sub(r'\s*[\[\(]\d{4}\s*-\s*\d{0,4}[\]\)]\s*', '', cleaned).strip()
        year_start = int(year_range_match.group(1))
        year_end = int(year_range_match.group(2)) if year_range_match.group(2) else None
        return (title, None, year_start, year_end)
    
    # Try to extract single year [YYYY] or (YYYY)
    year_match = re.search(r'[\[\(](\d{4})[\]\)]', cleaned)
    if year_match:
        title = re.sub(r'\s*[\[\(]\d{4}[\]\)]\s*', '', cleaned).strip()
        year = int(year_match.group(1))
        return (title, year, year, None)  # Could be movie or series start year
    
    # No year found
    return (cleaned, None, None, None)


def normalize_season_folder_name(folder_name: str) -> Optional[str]:
    """
    Normalize various season folder naming patterns to "Season XX" format.
    
    Examples:
        "Series 1" -> "Season 01"
        "S01" -> "Season 01" 
        "Season 1" -> "Season 01"
        "Season.01" -> "Season 01"
        "season1" -> "Season 01"
    
    Returns None if the folder doesn't appear to be a season folder.
    """
    folder_lower = folder_name.lower().strip()

    # Specials/extras folders -> "Specials" (must check BEFORE numeric patterns catch S00)
    specials_names = {
        "specials", "special", "s00",
        "extras", "extra",
        "behind the scenes", "behind_the_scenes", "bts",
        "featurettes", "featurette",
        "interviews", "interview",
        "deleted scenes", "deleted_scenes",
        "shorts", "short films",
        "bonus", "bonus features",
    }
    if folder_lower in specials_names:
        return "Specials"

    # Pattern: "Series X" or "Series XX" (British TV style)
    match = re.match(r'^series\s*(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"
    
    # Pattern: "S01", "S1", "s01"
    match = re.match(r'^s(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"
    
    # Pattern: "Season 1", "Season 01", "Season.01", "Season.1", "season1"
    match = re.match(r'^season[\s\.]*(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"
    
    # Pattern: "Staffel X" (German)
    match = re.match(r'^staffel\s*(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"
    
    # Pattern: "Temporada X" (Spanish)
    match = re.match(r'^temporada\s*(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"
    
    # Pattern: "Saison X" (French)
    match = re.match(r'^saison\s*(\d{1,2})$', folder_lower, re.IGNORECASE)
    if match:
        season_num = int(match.group(1))
        return f"Season {season_num:02d}"

    return None


def is_already_properly_named(name: str) -> bool:
    """
    Check if a file/folder name already matches our target format.
    Returns False for files that need renaming (bad patterns).
    """
    # First check if it matches a BAD pattern - these always need renaming
    for pattern in BAD_NAME_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return False  # Needs renaming

    # Then check if it matches a GOOD pattern
    for pattern in PROPER_NAME_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return True

    return False  # Unknown format, should be processed


def is_bdmv_folder(folder_path: Path) -> bool:
    """Check if a folder is a BDMV/Blu-ray disc structure."""
    try:
        folder_lower = folder_path.name.lower()

        # Check if this IS a BDMV folder
        if folder_lower in BDMV_INTERNAL_FOLDERS:
            return True

        # Check if folder contains BDMV structure
        for item in folder_path.iterdir():
            item_lower = item.name.lower()
            if item_lower in BDMV_MARKERS:
                return True
            if item.is_dir() and item_lower == 'bdmv':
                return True

        return False
    except (PermissionError, OSError):
        return False


def is_inside_bdmv_structure(file_path: Path) -> bool:
    """Check if a file is inside a BDMV structure (should not be moved)."""
    path_parts = [p.lower() for p in file_path.parts]
    for marker in BDMV_INTERNAL_FOLDERS:
        if marker in path_parts:
            return True
    return False


def get_bdmv_parent_folder(file_path: Path) -> Optional[Path]:
    """
    Get the parent folder of a BDMV structure that should be renamed.
    Returns the outermost folder that contains the BDMV structure.
    """
    current = file_path.parent
    bdmv_root = None

    while current.name:
        if current.name.lower() in BDMV_INTERNAL_FOLDERS:
            bdmv_root = current.parent
        elif is_bdmv_folder(current):
            bdmv_root = current
        current = current.parent

        # Safety: don't go more than 5 levels up
        if len(file_path.parts) - len(current.parts) > 5:
            break

    return bdmv_root


@dataclass
class RenamePlan:
    """A complete rename plan ready for preview/execution."""
    manifest: RenameManifest
    high_confidence: List[Dict]  # confidence >= threshold
    low_confidence: List[Dict]   # confidence < threshold
    unknown: List[Dict]          # media_type == "unknown"
    skipped: List[Dict]          # already named correctly
    folder_renames: List[Dict] = None  # parent folder renames needed

    def __post_init__(self):
        if self.folder_renames is None:
            self.folder_renames = []


def save_plan_to_file(plan: RenamePlan, config: Optional[dict] = None) -> str:
    """
    Save the rename plan to a text file for review before applying.

    Args:
        plan: The RenamePlan to save
        config: Optional config dict

    Returns:
        Path to the saved plan file
    """
    if config is None:
        config = load_config()

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_filename = f"rename_plan_{timestamp}.txt"

    # Save to the Documents/Renameify/logs directory (works in frozen mode)
    from .config import get_logs_dir
    plan_path = get_logs_dir() / plan_filename

    lines = []
    lines.append("=" * 80)
    lines.append("  RENAME PLAN - REVIEW BEFORE APPLYING")
    lines.append("=" * 80)
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Manifest ID: {plan.manifest.id}")
    lines.append(f"Root Path: {plan.manifest.root_path}")
    lines.append("")

    # Summary
    lines.append("-" * 80)
    lines.append("SUMMARY")
    lines.append("-" * 80)
    lines.append(f"  High confidence renames: {len(plan.high_confidence)}")
    lines.append(f"  Low confidence renames:  {len(plan.low_confidence)}")
    lines.append(f"  Unknown (skipped):       {len(plan.unknown)}")
    lines.append(f"  Already correct:         {len(plan.skipped)}")

    # Folder renames
    if plan.folder_renames:
        lines.append(f"  Folder renames needed:   {len(plan.folder_renames)}")

    total_subs = sum(len(item.get("subtitles", [])) for item in plan.high_confidence + plan.low_confidence)
    if total_subs > 0:
        lines.append(f"  Subtitles to rename:     {total_subs}")

    # Count moves vs renames
    moves = 0
    renames_only = 0
    for item in plan.high_confidence + plan.low_confidence:
        old_dir = Path(item["original_path"]).parent
        new_dir = Path(item["new_path"]).parent
        if old_dir != new_dir:
            moves += 1
        else:
            renames_only += 1

    lines.append("")
    lines.append(f"  Files to MOVE (different folder): {moves}")
    lines.append(f"  Files to RENAME (same folder):    {renames_only}")
    lines.append("")

    # Folder renames section
    if plan.folder_renames:
        lines.append("=" * 80)
        lines.append(f"FOLDER RENAMES ({len(plan.folder_renames)} folders)")
        lines.append("=" * 80)
        lines.append("")
        lines.append("  These folders will be renamed FIRST, before file operations:")
        lines.append("")
        for i, fr in enumerate(plan.folder_renames, 1):
            lines.append(f"  [{i}] {fr['type'].upper()}")
            lines.append(f"      OLD: {fr['original_name']}")
            lines.append(f"      NEW: {fr['new_name']}")
            lines.append(f"      Path: {fr['original_path']}")
            lines.append("")

    # High confidence operations
    if plan.high_confidence:
        lines.append("=" * 80)
        lines.append(f"HIGH CONFIDENCE OPERATIONS ({len(plan.high_confidence)} files)")
        lines.append("=" * 80)

        for i, item in enumerate(plan.high_confidence, 1):
            old_path = Path(item["original_path"])
            new_path = Path(item["new_path"])
            old_dir = old_path.parent
            new_dir = new_path.parent

            is_move = old_dir != new_dir

            lines.append("")
            lines.append(f"[{i}] {item['media_type'].upper()} - {item['title']} ({item['confidence']}% confidence)")
            lines.append(f"    OLD: {old_path}")
            lines.append(f"    NEW: {new_path}")

            if is_move:
                lines.append(f"    ACTION: MOVE (folder change)")
                lines.append(f"      From folder: {old_dir}")
                lines.append(f"      To folder:   {new_dir}")
            else:
                lines.append(f"    ACTION: RENAME (same folder)")

            # Subtitles
            for sub in item.get("subtitles", []):
                lang = sub.get("language", "unknown")
                lines.append(f"    + SUBTITLE ({lang}): {Path(sub['original_path']).name} -> {Path(sub['new_path']).name}")

    # Low confidence operations
    if plan.low_confidence:
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"LOW CONFIDENCE OPERATIONS - REVIEW CAREFULLY ({len(plan.low_confidence)} files)")
        lines.append("=" * 80)

        for i, item in enumerate(plan.low_confidence, 1):
            old_path = Path(item["original_path"])
            new_path = Path(item["new_path"])
            old_dir = old_path.parent
            new_dir = new_path.parent

            is_move = old_dir != new_dir

            lines.append("")
            lines.append(f"[{i}] {item['media_type'].upper()} - {item['title']} ({item['confidence']}% confidence)")
            if item.get("notes"):
                lines.append(f"    NOTE: {item['notes']}")
            lines.append(f"    OLD: {old_path}")
            lines.append(f"    NEW: {new_path}")

            if is_move:
                lines.append(f"    ACTION: MOVE")
            else:
                lines.append(f"    ACTION: RENAME")

    # Skipped files
    if plan.skipped:
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"SKIPPED FILES ({len(plan.skipped)} files)")
        lines.append("=" * 80)

        for item in plan.skipped:
            reason = item.get("reason", "Unknown reason")
            lines.append(f"  - {Path(item['original_path']).name}")
            lines.append(f"    Reason: {reason}")

    # Footer
    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF PLAN")
    lines.append("=" * 80)
    lines.append("")
    lines.append("To apply this plan, use the 'Apply Renames' option in the menu.")
    lines.append("All operations can be rolled back using the manifest ID.")
    lines.append("")

    # Write to file
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return str(plan_path)


def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename."""
    # Windows forbidden characters: \ / : * ? " < > |
    invalid_chars = r'[\\/:*?"<>|]'
    sanitized = re.sub(invalid_chars, '', name)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    # Collapse multiple spaces
    sanitized = re.sub(r'\s+', ' ', sanitized)
    return sanitized


def generate_rename_plan(
    media_files: List[MediaFile],
    media_infos: List[MediaInfo],
    root_path: str,
    config: Optional[dict] = None,
    force: bool = False
) -> RenamePlan:
    """
    Generate a complete rename plan from scanned files and GPT identifications.

    Args:
        media_files: List of scanned MediaFile objects
        media_infos: List of MediaInfo from GPT
        root_path: The root scanning path
        config: Optional config dict
        force: If True, skip 'already properly named' check and process all files
        media_infos: List of MediaInfo from GPT
        root_path: The root scanning path
        config: Optional config dict

    Returns:
        RenamePlan with categorized operations
    """
    if config is None:
        config = load_config()

    threshold = config.get("confidence_threshold", 80)

    # Create multiple lookup strategies for matching LLM results to scanned files
    info_lookup = {}  # exact original_filename -> MediaInfo
    info_by_path = {}  # original_path -> MediaInfo
    info_by_stem = {}  # lowercase stem -> MediaInfo
    info_by_norm = {}  # normalized name -> MediaInfo

    for info in media_infos:
        info_lookup[info.original_filename] = info
        if info.original_path:
            info_by_path[info.original_path] = info
        # Store by stem (strip extension from what the LLM returned)
        stem = re.sub(r'\.[^.]+$', '', info.original_filename).lower()
        info_by_stem[stem] = info
        # Normalized: collapse separators
        norm = re.sub(r'[\.\-_]+', ' ', stem).strip()
        info_by_norm[norm] = info

    def _find_info(media_file):
        """Try multiple strategies to find the MediaInfo for a MediaFile."""
        fn = media_file.filename  # stem, no extension
        fn_with_ext = fn + media_file.extension

        # 1. Exact match on filename with extension (what we now send to LLM)
        if fn_with_ext in info_lookup:
            return info_lookup[fn_with_ext]
        # 2. Exact match on stem only
        if fn in info_lookup:
            return info_lookup[fn]
        # 3. Match by full path
        path_str = str(media_file.path)
        if path_str in info_by_path:
            return info_by_path[path_str]
        # 4. Case-insensitive stem match
        fn_lower = fn.lower()
        if fn_lower in info_by_stem:
            return info_by_stem[fn_lower]
        # 5. Normalized match
        fn_norm = re.sub(r'[\.\-_]+', ' ', fn_lower).strip()
        if fn_norm in info_by_norm:
            return info_by_norm[fn_norm]
        # 6. Substring / fuzzy containment
        for key, info in info_lookup.items():
            key_lower = key.lower()
            key_stem = re.sub(r'\.[^.]+$', '', key_lower)
            if fn_lower == key_stem or fn_lower in key_lower or key_stem in fn_lower:
                return info
        return None

    plan_items = []
    high_confidence = []
    low_confidence = []
    unknown = []
    skipped = []

    for media_file in media_files:
        info = _find_info(media_file)

        if not info:
            # No GPT info found, skip
            skipped.append({
                "original_path": str(media_file.path),
                "reason": "No GPT identification available"
            })
            continue

        # Check if file is inside a BDMV structure - don't move internal files
        if is_inside_bdmv_structure(media_file.path):
            bdmv_parent = get_bdmv_parent_folder(media_file.path)
            if bdmv_parent:
                # Only rename the BDMV parent folder, not internal files
                skipped.append({
                    "original_path": str(media_file.path),
                    "reason": f"Inside BDMV structure (parent: {bdmv_parent.name})"
                })
                continue

        # Check if file/folder is already properly named (smart skip for re-runs)
        # Skip this check if force=True
        if not force:
            current_filename = media_file.path.stem
            current_parent = media_file.path.parent.name

            # Check if the filename already matches our format
            if is_already_properly_named(current_filename) or is_already_properly_named(f"{current_filename}{media_file.extension}"):
                # Also check if parent folder structure looks correct
                parent_looks_correct = (
                    is_already_properly_named(current_parent) or
                    current_parent.lower().startswith("season")
                )
                if parent_looks_correct:
                    skipped.append({
                        "original_path": str(media_file.path),
                        "reason": "Already matches target naming format"
                    })
                    continue

        # Generate new filename
        new_filename = sanitize_filename(format_media_info(info, config))
        new_filename_with_ext = new_filename + media_file.extension

        # Files are always renamed in-place (same directory) unless Plex specials
        # consolidation needs to move them to the top-level Specials folder.
        new_path = media_file.path.parent / new_filename_with_ext

        # --- Plex specials consolidation ---
        # Plex requires that all specials (season 0) live in a single "Specials"
        # folder directly under the show root, NOT inside Season XX sub-folders.
        platform = config.get("platform", "generic")
        is_special = (
            info.media_type == "series" and
            ((info.season == 0) or (getattr(info, 'special_type', None) is not None))
        )
        if platform == "plex" and is_special:
            show_root = _find_show_root_for_specials(media_file.path, root_path)
            if show_root is not None:
                target_specials_dir = show_root / "Specials"
                # Only redirect if not already in the correct Specials folder
                if media_file.path.parent != target_specials_dir:
                    new_path = target_specials_dir / new_filename_with_ext

        # Check if already correctly named (exact path match)
        if str(media_file.path) == str(new_path):
            skipped.append({
                "original_path": str(media_file.path),
                "reason": "Already correctly named"
            })
            continue

        # Handle subtitles - generate rename operations for associated subtitles
        subtitle_operations = []
        if config.get("rename_subtitles", True) and hasattr(media_file, 'subtitles') and media_file.subtitles:
            for sub in media_file.subtitles:
                # Build new subtitle filename with same base name
                lang_suffix = f".{sub.language}" if sub.language else ""
                new_sub_filename = f"{new_filename}{lang_suffix}{sub.extension}"

                # Subtitles are renamed in-place alongside the video file
                new_sub_path = media_file.path.parent / new_sub_filename

                if str(sub.path) != str(new_sub_path):
                    subtitle_operations.append({
                        "original_path": str(sub.path),
                        "new_path": str(new_sub_path),
                        "type": "subtitle",
                        "language": sub.language
                    })

        plan_item = {
            "original_path": str(media_file.path),
            "new_path": str(new_path),
            "media_type": info.media_type,
            "title": info.title,
            "year": info.year,
            "season": info.season,
            "episode": info.episode,
            "confidence": info.confidence,
            "notes": info.notes,
            "special_type": getattr(info, 'special_type', None),
            "subtitles": subtitle_operations  # Include subtitle operations
        }

        plan_items.append(plan_item)

        # Categorize by confidence
        if info.media_type == "unknown":
            unknown.append(plan_item)
        elif info.confidence >= threshold:
            high_confidence.append(plan_item)
        else:
            low_confidence.append(plan_item)

    # Detect if parent folders need renaming BEFORE creating manifest
    folder_renames = []

    # Check the root path itself - is it a scene-release folder or needs cleaning?
    root = Path(root_path)
    root_name = root.name

    # Check if root folder needs renaming (has junk in name)
    if is_scene_release_folder(root_name) and media_infos:
        # Use the first media info to determine what the folder should be named
        first_info = media_infos[0]
        if first_info.media_type == "series":
            year_range = first_info.year_range
            if year_range:
                correct_name = f"{first_info.title} [{year_range}]"
            else:
                correct_name = first_info.title
        elif first_info.media_type == "movie":
            if first_info.year:
                correct_name = f"{first_info.title} [{first_info.year}]"
            else:
                correct_name = first_info.title
        else:
            correct_name = None

        if correct_name and correct_name != root_name:
            new_root_path = root.parent / sanitize_filename(correct_name)
            folder_renames.append({
                "original_path": str(root),
                "new_path": str(new_root_path),
                "original_name": root_name,
                "new_name": sanitize_filename(correct_name),
                "type": "series_folder" if first_info.media_type == "series" else "movie_folder",
                "confidence": first_info.confidence
            })

            # Update all file paths in the plan to reflect the new root
            for item in plan_items:
                old_path = item["original_path"]
                new_path = item["new_path"]
                # Update new_path to use the corrected root folder
                item["new_path"] = new_path.replace(str(root), str(new_root_path))

    # Also check intermediate folders in the path for scene-release names or season folder normalization
    # This handles cases like: D:\SeriesName\Scene.Release.Folder\Season 1\file.mkv
    # Or: D:\Series\Series 1\file.mkv (British "Series X" naming)
    checked_folders = set()
    for media_file in media_files:
        current = media_file.path.parent
        while current != root and current.name:
            folder_name = current.name
            folder_path_str = str(current)
            
            if folder_path_str not in checked_folders:
                checked_folders.add(folder_path_str)
                
                # Check if this is a season folder that needs normalization
                # (e.g., "Series 1" -> "Season 01", "S01" -> "Season 01")
                normalized_season = normalize_season_folder_name(folder_name)
                if normalized_season and normalized_season != folder_name:
                    # This is a season folder that needs renaming
                    folder_renames.append({
                        "original_path": str(current),
                        "new_path": str(current.parent / normalized_season),
                        "original_name": folder_name,
                        "new_name": normalized_season,
                        "type": "season_folder",
                        "confidence": 90  # High confidence for season folder normalization
                    })
                elif is_scene_release_folder(folder_name):
                    # This intermediate folder needs renaming
                    # Try to determine correct name from the files inside
                    info = info_lookup.get(media_file.filename)
                    if info and info.season:
                        # It's likely a season folder that looks like a scene release
                        correct_name = f"Season {info.season:02d}"
                        if folder_name != correct_name:
                            folder_renames.append({
                                "original_path": str(current),
                                "new_path": str(current.parent / correct_name),
                                "original_name": folder_name,
                                "new_name": correct_name,
                                "type": "season_folder",
                                "confidence": info.confidence if info else 50
                            })
            current = current.parent

    # Create manifest with folder_renames included
    manifest = create_manifest_from_plan(plan_items, root_path, folder_renames)

    return RenamePlan(
        manifest=manifest,
        high_confidence=high_confidence,
        low_confidence=low_confidence,
        unknown=unknown,
        skipped=skipped,
        folder_renames=folder_renames
    )


def format_rename_preview(plan: RenamePlan, show_all: bool = False) -> str:
    """Format the rename plan for preview display."""
    lines = [
        f"\n{'='*80}",
        f"  RENAME PREVIEW",
        f"{'='*80}",
        f"\n  Summary:",
        f"    ✓ High confidence (will rename):  {len(plan.high_confidence)}",
        f"    ? Low confidence (needs review):  {len(plan.low_confidence)}",
        f"    ✗ Unknown (skipped):              {len(plan.unknown)}",
        f"    - Already correct (skipped):      {len(plan.skipped)}",
    ]

    # Folder renames
    if plan.folder_renames:
        lines.append(f"    📁 Folders to rename:             {len(plan.folder_renames)}")

    lines.append(f"    ─────────────────────────────────")
    lines.append(f"    Total operations:                 {len(plan.high_confidence) + len(plan.low_confidence)}")

    # Count subtitles
    total_subs = sum(len(item.get("subtitles", [])) for item in plan.high_confidence + plan.low_confidence)
    if total_subs > 0:
        lines.append(f"    📝 Subtitles to rename:           {total_subs}")

    # Folder renames section
    if plan.folder_renames:
        lines.append(f"\n  {'─'*76}")
        lines.append(f"  📁 FOLDER RENAMES (will be renamed FIRST):")
        lines.append(f"  {'─'*76}")
        for fr in plan.folder_renames:
            lines.append(f"\n  [{fr['confidence']}%] {fr['type'].upper()}")
            lines.append(f"       OLD: {fr['original_name']}")
            lines.append(f"       NEW: {fr['new_name']}")

    # High confidence items
    if plan.high_confidence:
        lines.append(f"\n  {'─'*76}")
        lines.append(f"  HIGH CONFIDENCE RENAMES ({len(plan.high_confidence)} files):")
        lines.append(f"  {'─'*76}")

        display_items = plan.high_confidence if show_all else plan.high_confidence[:10]
        for item in display_items:
            old_name = Path(item["original_path"]).name
            new_name = Path(item["new_path"]).name
            sub_count = len(item.get("subtitles", []))
            sub_info = f" +{sub_count} subs" if sub_count > 0 else ""
            lines.append(f"\n  [{item['confidence']}%] {item['media_type'].upper()}{sub_info}")
            lines.append(f"    FROM: {old_name}")
            lines.append(f"    TO:   {new_name}")
            if item.get("notes"):
                lines.append(f"    NOTE: {item['notes']}")

        if not show_all and len(plan.high_confidence) > 10:
            lines.append(f"\n  ... and {len(plan.high_confidence) - 10} more (use --all to see all)")

    # Low confidence items
    if plan.low_confidence:
        lines.append(f"\n  {'─'*76}")
        lines.append(f"  ⚠️  LOW CONFIDENCE - NEEDS REVIEW ({len(plan.low_confidence)} files):")
        lines.append(f"  {'─'*76}")

        for item in plan.low_confidence:
            old_name = Path(item["original_path"]).name
            new_name = Path(item["new_path"]).name
            sub_count = len(item.get("subtitles", []))
            sub_info = f" +{sub_count} subs" if sub_count > 0 else ""
            lines.append(f"\n  [{item['confidence']}%] {item['media_type'].upper()}{sub_info}")
            lines.append(f"    FROM: {old_name}")
            lines.append(f"    TO:   {new_name}")
            if item.get("notes"):
                lines.append(f"    NOTE: {item['notes']}")

    # Unknown items
    if plan.unknown:
        lines.append(f"\n  {'─'*76}")
        lines.append(f"  ❌ UNKNOWN - WILL BE SKIPPED ({len(plan.unknown)} files):")
        lines.append(f"  {'─'*76}")

        for item in plan.unknown[:5]:
            old_name = Path(item["original_path"]).name
            lines.append(f"    - {old_name}")

        if len(plan.unknown) > 5:
            lines.append(f"    ... and {len(plan.unknown) - 5} more")

    lines.append(f"\n{'='*80}")
    lines.append(f"  To apply high-confidence renames: renamer apply")
    lines.append(f"  To apply ALL renames (incl. low): renamer apply --include-low-confidence")
    lines.append(f"{'='*80}\n")

    return "\n".join(lines)


def execute_rename_plan(
    manifest: RenameManifest,
    include_low_confidence: bool = False,
    config: Optional[dict] = None,
    folder_renames: List[Dict] = None
) -> Tuple[int, int, List[str]]:
    """
    Execute the rename operations in a manifest.

    Args:
        manifest: The manifest to execute
        include_low_confidence: Whether to include low-confidence renames
        config: Optional config dict
        folder_renames: List of folder rename operations to execute first

    Returns:
        Tuple of (successful_count, failed_count, error_messages)
    """
    if config is None:
        config = load_config()

    threshold = config.get("confidence_threshold", 80)

    # Save manifest first (for rollback)
    save_manifest(manifest, config)

    successful = 0
    failed = 0
    errors = []

    # Execute folder renames FIRST (before file operations)
    folder_path_mapping = {}  # Track old -> new path mappings
    if folder_renames:
        for fr in folder_renames:
            try:
                old_folder = Path(fr["original_path"])
                new_folder = Path(fr["new_path"])

                if old_folder.exists() and not new_folder.exists():
                    old_folder.rename(new_folder)
                    folder_path_mapping[str(old_folder)] = str(new_folder)
                    successful += 1
                elif new_folder.exists():
                    # Target already exists - might be a duplicate
                    errors.append(f"Folder already exists: {new_folder}")
                else:
                    errors.append(f"Source folder not found: {old_folder}")
            except Exception as e:
                failed += 1
                errors.append(f"Failed to rename folder {fr['original_name']}: {str(e)}")

    for op in manifest.operations:
        # Skip low confidence if not included
        if not include_low_confidence and op.get("confidence", 0) < threshold:
            continue

        # Skip unknown
        if op.get("media_type") == "unknown":
            continue

        original = Path(op["original_path"])
        new = Path(op["new_path"])

        # Update paths if parent folder was renamed
        for old_folder, new_folder in folder_path_mapping.items():
            if str(original).startswith(old_folder):
                original = Path(str(original).replace(old_folder, new_folder, 1))
            if str(new).startswith(old_folder):
                new = Path(str(new).replace(old_folder, new_folder, 1))

        try:
            # Create target directory if needed
            new.parent.mkdir(parents=True, exist_ok=True)

            # Check if target already exists
            if new.exists():
                # Add number suffix to avoid overwrite
                base = new.stem
                ext = new.suffix
                counter = 1
                while new.exists():
                    new = new.parent / f"{base} ({counter}){ext}"
                    counter += 1

            # Perform rename/move for video file
            shutil.move(str(original), str(new))
            successful += 1

            # Rename associated subtitles
            subtitle_ops = op.get("subtitles", [])
            for sub_op in subtitle_ops:
                try:
                    sub_original = Path(sub_op["original_path"])
                    sub_new = Path(sub_op["new_path"])

                    if sub_original.exists():
                        sub_new.parent.mkdir(parents=True, exist_ok=True)

                        # Handle existing subtitle files
                        if sub_new.exists():
                            base = sub_new.stem
                            ext = sub_new.suffix
                            counter = 1
                            while sub_new.exists():
                                sub_new = sub_new.parent / f"{base} ({counter}){ext}"
                                counter += 1

                        shutil.move(str(sub_original), str(sub_new))
                except Exception as sub_e:
                    # Log subtitle errors but don't fail the operation
                    sub_name = sub_op.get("original_path", "unknown")
                    errors.append(f"Subtitle warning - {Path(sub_name).name}: {str(sub_e)}")

            # Clean up empty source directories after moving
            try:
                original_parent = original.parent
                root = Path(manifest.root_path)
                # Remove empty parent directories up to root
                while original_parent != root and original_parent.exists():
                    if not any(original_parent.iterdir()):
                        original_parent.rmdir()
                        original_parent = original_parent.parent
                    else:
                        break
            except Exception:
                pass  # Ignore errors cleaning up directories

        except Exception as e:
            failed += 1
            errors.append(f"Failed to rename {original.name}: {str(e)}")

    # Update manifest status
    update_manifest_status(manifest.id, applied=True, config=config)

    return successful, failed, errors


def execute_rollback(manifest: RenameManifest, config: Optional[dict] = None) -> Tuple[int, int, List[str]]:
    """
    Rollback a previously applied rename operation.

    Args:
        manifest: The manifest to rollback
        config: Optional config dict

    Returns:
        Tuple of (successful_count, failed_count, error_messages)
    """
    if not manifest.applied:
        return 0, 0, ["This manifest has not been applied yet."]

    if manifest.rolled_back:
        return 0, 0, ["This manifest has already been rolled back."]

    successful = 0
    failed = 0
    errors = []

    # Reverse operations
    for op in manifest.operations:
        original = Path(op["original_path"])
        new = Path(op["new_path"])

        # Skip if new file doesn't exist (wasn't renamed)
        if not new.exists():
            continue

        try:
            # Restore original directory if needed
            original.parent.mkdir(parents=True, exist_ok=True)

            # Move back
            shutil.move(str(new), str(original))
            successful += 1

            # Try to remove empty directories
            try:
                new_parent = new.parent
                while new_parent != Path(manifest.root_path):
                    if new_parent.exists() and not any(new_parent.iterdir()):
                        new_parent.rmdir()
                    new_parent = new_parent.parent
            except:
                pass  # Ignore errors cleaning up directories

        except Exception as e:
            failed += 1
            errors.append(f"Failed to restore {new.name}: {str(e)}")

    # Update manifest status
    update_manifest_status(manifest.id, rolled_back=True, config=config)

    return successful, failed, errors

