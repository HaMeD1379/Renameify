"""
Smart folder filtering module - uses GPT to pre-classify folders before deep scanning.
This saves significant time by avoiding scanning non-media folders.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.config import load_config, get_api_key


@dataclass
class FolderClassification:
    """Classification result for a folder."""
    path: str
    name: str
    classification: str  # "media", "personal", "system", "other", "unknown"
    confidence: int  # 0-100
    reason: str
    should_scan: bool


FOLDER_FILTER_PROMPT = """You are a folder classification expert. Analyze these folder names and classify each one.

For each folder, determine if it likely contains movies/TV series that should be renamed, or if it's something else.

Classifications:
- "media": Likely contains movies, TV shows, or video content (SCAN THIS)
- "personal": Personal files, photos, documents (SKIP)
- "system": System folders, program files, backups (SKIP)  
- "other": Other non-media content like games, music, software (SKIP)
- "mixed": Could contain media mixed with other content (SCAN but warn)

Look for clues in folder names:
- Movie/Series names with years: "The Matrix (1999)", "Breaking Bad S01"
- Quality indicators: 720p, 1080p, BluRay, WEB-DL, x264
- Media-related words: Movies, Series, TV, Shows, Films, Videos
- Scene release patterns: Movie.Name.2020.1080p.BluRay-GROUP

Return ONLY a JSON array, no markdown:
[{"name": "folder_name", "classification": "media|personal|system|other|mixed", "confidence": 0-100, "reason": "brief reason"}]"""


def classify_folders_with_gpt(
    folder_names: List[Tuple[str, str]],  # List of (folder_name, full_path)
    config: Optional[dict] = None
) -> List[FolderClassification]:
    """
    Use GPT to classify folders as media or non-media.

    Args:
        folder_names: List of (folder_name, full_path) tuples
        config: Optional config dict

    Returns:
        List of FolderClassification objects
    """
    if OpenAI is None:
        raise ImportError("OpenAI package not installed")

    if config is None:
        config = load_config()

    api_key = get_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    # Format folder list
    folder_list = "\n".join([f"- {name}" for name, _ in folder_names])

    # Create path lookup
    path_lookup = {name: path for name, path in folder_names}

    try:
        response = client.chat.completions.create(
            model=config.get("openai_model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": FOLDER_FILTER_PROMPT},
                {"role": "user", "content": f"Classify these folders:\n{folder_list}"}
            ],
            temperature=0.1,
            max_tokens=2048
        )

        content = response.choices[0].message.content.strip()

        # Clean up response
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        results = json.loads(content)

        classifications = []
        for item in results:
            name = item.get("name", "")
            classification = item.get("classification", "unknown")
            should_scan = classification in ("media", "mixed")

            classifications.append(FolderClassification(
                path=path_lookup.get(name, ""),
                name=name,
                classification=classification,
                confidence=item.get("confidence", 50),
                reason=item.get("reason", ""),
                should_scan=should_scan
            ))

        return classifications

    except json.JSONDecodeError as e:
        # If GPT response fails, assume all folders might be media
        return [
            FolderClassification(
                path=path,
                name=name,
                classification="unknown",
                confidence=50,
                reason="GPT classification failed",
                should_scan=True
            )
            for name, path in folder_names
        ]
    except Exception as e:
        raise RuntimeError(f"Folder classification error: {e}")


def quick_classify_folder(folder_name: str, config: Optional[dict] = None) -> Tuple[bool, str]:
    """
    Quick local heuristic classification without GPT.
    Use this for obvious cases to save API calls.

    Args:
        folder_name: Name of the folder
        config: Optional config dict

    Returns:
        Tuple of (should_scan, reason)
    """
    if config is None:
        config = load_config()

    folder_lower = folder_name.lower()

    # Check excluded folder names first
    excluded_names = [n.lower() for n in config.get("excluded_folder_names", [])]
    if folder_lower in excluded_names:
        return False, f"Excluded folder name: {folder_name}"

    # Check for common non-media patterns FIRST (before year check)
    import re
    non_media_patterns = [
        # Hidden/System
        (r'^\.', "Hidden folder"),
        (r'\$', "System folder"),

        # Backup/Archive
        (r'\bbackup', "Backup folder"),
        (r'\bbak\b', "Backup folder"),
        (r'\bold\b', "Old/archive folder"),
        (r'\bcopy\b', "Copy folder"),
        (r'\barchive', "Archive folder"),

        # Study/Education/Tutorials - THIS IS THE KEY ADDITION
        (r'\bstudy', "Study/Education folder"),
        (r'\bstudywithme', "Study folder"),
        (r'\blearn', "Learning folder"),
        (r'\btutorial', "Tutorial folder"),
        (r'\bcourse', "Course folder"),
        (r'\btraining', "Training folder"),
        (r'\blesson', "Lesson folder"),
        (r'\blecture', "Lecture folder"),
        (r'\beducation', "Education folder"),
        (r'\bebook', "Ebook folder"),
        (r'\bbook\b', "Books folder"),
        (r'\bbooks\b', "Books folder"),
        (r'\bpdf\b', "PDF/Documents folder"),
        (r'\budemy', "Online course folder"),
        (r'\bcoursera', "Online course folder"),
        (r'\blynda', "Online course folder"),
        (r'\bskillshare', "Online course folder"),
        (r'\bpluralsight', "Online course folder"),
        (r'\bfreecodecamp', "Coding tutorial folder"),
        (r'\bcoding', "Coding folder"),
        (r'\bprogramming', "Programming folder"),
        (r'\bwebdev', "Web development folder"),

        # Software/Apps
        (r'\binstall', "Install folder"),
        (r'\bsetup\b', "Setup folder"),
        (r'\bportable\b', "Portable app"),
        (r'\bcrack\b', "Non-media"),
        (r'\bkeygen\b', "Non-media"),
        (r'\bpatch\b', "Patch folder"),
        (r'\bsoftware', "Software folder"),
        (r'\bprogram', "Programs folder"),
        (r'\bapplication', "Applications folder"),
        (r'\bapp\b', "Apps folder"),
        (r'\bapps\b', "Apps folder"),
        (r'\bdriver', "Drivers folder"),
        (r'\btool\b', "Tools folder"),
        (r'\btools\b', "Tools folder"),
        (r'\butilities', "Utilities folder"),

        # Documents/Personal
        (r'\bdocument', "Documents folder"),
        (r'\bphoto', "Photos folder"),
        (r'\bpicture', "Pictures folder"),
        (r'\bimage', "Images folder"),
        (r'\bscreenshot', "Screenshots folder"),
        (r'\bwallpaper', "Wallpapers folder"),
        (r'\bpersonal', "Personal folder"),
        (r'\bprivate', "Private folder"),
        (r'\bfamily', "Family folder"),
        (r'\bwork\b', "Work folder"),
        (r'\boffice', "Office folder"),
        (r'\bproject', "Project folder"),

        # Music/Audio
        (r'\bmusic\b', "Music folder"),
        (r'\baudio\b', "Audio folder"),
        (r'\bmp3\b', "Music folder"),
        (r'\bflac\b', "Music folder"),
        (r'\bpodcast', "Podcast folder"),
        (r'\baudiobook', "Audiobook folder"),
        (r'\bsound', "Sound folder"),

        # Games
        (r'\bgame', "Games folder"),
        (r'\bsteam\b', "Games folder"),
        (r'\borigin\b', "Games folder"),
        (r'\bepic\b', "Games folder"),
        (r'\bubisoft', "Games folder"),
        (r'\bgog\b', "Games folder"),
        (r'\bemulator', "Emulator folder"),
        (r'\brom\b', "ROMs folder"),
        (r'\broms\b', "ROMs folder"),

        # Downloads/Temp
        (r'\btorrent', "Torrent folder"),
        (r'\bincomplete', "Incomplete downloads"),
        (r'\bdownload', "Downloads folder"),
        (r'\brecycle', "Recycle bin"),
        (r'\btemp\b', "Temp folder"),
        (r'\btmp\b', "Temp folder"),
        (r'\bcache\b', "Cache folder"),

        # Development
        (r'\bnode_modules', "Node modules"),
        (r'\bvenv\b', "Virtual environment"),
        (r'\.venv', "Virtual environment"),
        (r'\bgit\b', "Git folder"),
        (r'\bsrc\b', "Source code"),
        (r'\bsource\b', "Source code"),
        (r'\bbuild\b', "Build folder"),
        (r'\bdist\b', "Distribution folder"),
        (r'\bvendor', "Vendor folder"),
        (r'\blib\b', "Library folder"),
        (r'\blibs\b', "Libraries folder"),
    ]

    for pattern, reason in non_media_patterns:
        if re.search(pattern, folder_lower):
            return False, reason

    # Now check for media hints - these are strong signals
    media_hints = [h.lower() for h in config.get("media_folder_hints", [])]
    for hint in media_hints:
        if hint in folder_lower:
            return True, f"Media hint found: {hint}"

    # Check for quality indicators (strong media signal)
    quality_patterns = [
        r'\b720p\b', r'\b1080p\b', r'\b2160p\b', r'\b4k\b',
        r'\bbluray\b', r'\bblu-ray\b', r'\bweb-?dl\b', r'\bhdtv\b',
        r'\bdvdrip\b', r'\bbrrip\b', r'\bwebrip\b',
        r'\bx264\b', r'\bx265\b', r'\bhevc\b', r'\bhdr\b',
        r'\bremux\b', r'\batmos\b', r'\bdts\b'
    ]
    for pattern in quality_patterns:
        if re.search(pattern, folder_lower):
            return True, "Quality indicator found"

    # Check for season/episode patterns (strong media signal)
    season_pattern = r'\b[Ss]\d{1,2}|\bseason\s*\d|\b[Ee]\d{2}\b'
    if re.search(season_pattern, folder_name):
        return True, "Season/Episode pattern found"

    # Check for year pattern - but only if it looks like a title
    # Pattern: has year AND some text before it (not just "2024" or "Backup 2024")
    year_with_title = r'^.{3,}\s*[\(\[]?(19|20)\d{2}[\)\]]?'
    if re.search(year_with_title, folder_name):
        # Make sure it doesn't look like a backup/personal folder
        if not any(word in folder_lower for word in ['backup', 'personal', 'private', 'copy', 'old']):
            return True, "Title with year (likely media)"

    # Default: unknown, scan to be safe but with low confidence
    return True, "No clear classification"


def get_top_level_folders(root_path: str) -> List[Tuple[str, str]]:
    """
    Get immediate subdirectories of a path.

    Args:
        root_path: Root directory to list

    Returns:
        List of (folder_name, full_path) tuples
    """
    root = Path(root_path)
    folders = []

    try:
        for item in root.iterdir():
            if item.is_dir():
                folders.append((item.name, str(item)))
    except PermissionError:
        pass
    except Exception:
        pass

    return folders


def smart_filter_folders(
    root_path: str,
    config: Optional[dict] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
    use_gpt: bool = True
) -> Tuple[List[str], List[str], List[FolderClassification]]:
    """
    Smart filter folders to identify which ones to scan.
    Uses heuristics first, then GPT for uncertain ones.

    Args:
        root_path: Root directory to analyze
        config: Optional config dict
        progress_callback: Optional callback for status updates
        use_gpt: Whether to use GPT for classification

    Returns:
        Tuple of (folders_to_scan, folders_to_skip, classifications)
    """
    if config is None:
        config = load_config()

    if progress_callback:
        progress_callback("Getting folder list...")

    # Get top-level folders
    all_folders = get_top_level_folders(root_path)

    if not all_folders:
        return [], [], []

    folders_to_scan = []
    folders_to_skip = []
    classifications = []
    uncertain_folders = []

    if progress_callback:
        progress_callback(f"Analyzing {len(all_folders)} folders...")

    # First pass: quick heuristic classification
    for name, path in all_folders:
        should_scan, reason = quick_classify_folder(name, config)

        # If clearly media or clearly not, decide now
        if "Media hint found" in reason or "quality indicator" in reason.lower() or "Season" in reason:
            folders_to_scan.append(path)
            classifications.append(FolderClassification(
                path=path, name=name, classification="media",
                confidence=85, reason=reason, should_scan=True
            ))
        elif "Excluded" in reason or "Non-media pattern" in reason:
            folders_to_skip.append(path)
            classifications.append(FolderClassification(
                path=path, name=name, classification="other",
                confidence=80, reason=reason, should_scan=False
            ))
        else:
            # Uncertain - check subfolders first before GPT
            uncertain_folders.append((name, path))

    # Second pass: For uncertain folders, peek at subfolders/files to decide
    still_uncertain = []
    if progress_callback:
        progress_callback(f"Checking {len(uncertain_folders)} uncertain folders for media content...")

    for name, path in uncertain_folders:
        decision, reason = check_folder_contents(path, config)

        if decision == "media":
            folders_to_scan.append(path)
            classifications.append(FolderClassification(
                path=path, name=name, classification="media",
                confidence=75, reason=reason, should_scan=True
            ))
        elif decision == "skip":
            folders_to_skip.append(path)
            classifications.append(FolderClassification(
                path=path, name=name, classification="other",
                confidence=75, reason=reason, should_scan=False
            ))
        else:
            # Still uncertain after checking contents
            still_uncertain.append((name, path))

    # Third pass: use GPT for remaining uncertain folders
    if still_uncertain and use_gpt and config.get("smart_folder_filter", True):
        if progress_callback:
            progress_callback(f"Using GPT to classify {len(still_uncertain)} remaining uncertain folders...")

        try:
            gpt_classifications = classify_folders_with_gpt(still_uncertain, config)

            for fc in gpt_classifications:
                classifications.append(fc)
                if fc.should_scan:
                    folders_to_scan.append(fc.path)
                else:
                    folders_to_skip.append(fc.path)

        except Exception as e:
            # GPT failed, scan all uncertain folders to be safe
            if progress_callback:
                progress_callback(f"GPT classification failed: {e}. Scanning all uncertain folders.")

            for name, path in still_uncertain:
                folders_to_scan.append(path)
                classifications.append(FolderClassification(
                    path=path, name=name, classification="unknown",
                    confidence=50, reason="GPT failed, scanning to be safe",
                    should_scan=True
                ))
    else:
        # No GPT, scan all uncertain folders
        for name, path in still_uncertain:
            folders_to_scan.append(path)
            classifications.append(FolderClassification(
                path=path, name=name, classification="unknown",
                confidence=50, reason="No GPT classification",
                should_scan=True
            ))

    return folders_to_scan, folders_to_skip, classifications


def check_folder_contents(folder_path: str, config: dict) -> Tuple[str, str]:
    """
    Check folder contents (subfolders and files) to determine if it's media.

    Args:
        folder_path: Path to check
        config: Config dict

    Returns:
        Tuple of (decision, reason) where decision is "media", "skip", or "uncertain"
    """
    video_extensions = set(ext.lower() for ext in config.get("video_extensions", []))

    try:
        path = Path(folder_path)
        subfolders = []
        video_count = 0
        non_media_signals = 0
        media_signals = 0

        # Quick scan - don't go too deep
        for item in path.iterdir():
            if item.is_dir():
                subfolders.append(item.name)
                # Check subfolder name
                should_scan, reason = quick_classify_folder(item.name, config)
                if not should_scan:
                    non_media_signals += 1
                elif "Media hint" in reason or "Quality" in reason or "Season" in reason:
                    media_signals += 1
            elif item.is_file():
                if item.suffix.lower() in video_extensions:
                    video_count += 1
                    media_signals += 1

        # Decision logic
        if video_count > 0:
            return "media", f"Contains {video_count} video file(s)"

        if media_signals > non_media_signals and media_signals > 0:
            return "media", f"Subfolders suggest media content"

        if non_media_signals > media_signals and non_media_signals > 0:
            return "skip", f"Subfolders suggest non-media content"

        # Check if subfolders have any media-like patterns
        for subfolder in subfolders[:10]:  # Check first 10 subfolders
            # Look for clear media patterns
            import re
            if re.search(r'\b(720p|1080p|2160p|4k|bluray|webrip|x264|x265|S\d{2}E\d{2})', subfolder, re.IGNORECASE):
                return "media", f"Subfolder '{subfolder}' has media pattern"

        return "uncertain", "No clear signals from contents"

    except PermissionError:
        return "uncertain", "Permission denied"
    except Exception as e:
        return "uncertain", f"Error checking: {str(e)}"


def format_classification_report(classifications: List[FolderClassification]) -> str:
    """Format classification results for display."""
    lines = [
        "\n" + "=" * 70,
        "  FOLDER CLASSIFICATION REPORT",
        "=" * 70
    ]

    # Group by classification
    media = [c for c in classifications if c.classification == "media"]
    skipped = [c for c in classifications if c.classification != "media" and not c.should_scan]
    mixed = [c for c in classifications if c.classification == "mixed"]

    if media:
        lines.append(f"\n  📁 MEDIA FOLDERS ({len(media)}) - Will scan:")
        # Show first 15 media folders with truncation for the rest
        for c in media[:15]:
            lines.append(f"    ✓ {c.name} ({c.confidence}%) - {c.reason}")
        if len(media) > 15:
            lines.append(f"    ... and {len(media) - 15} more media folders")

    if mixed:
        lines.append(f"\n  ⚠️  MIXED FOLDERS ({len(mixed)}) - Will scan with caution:")
        for c in mixed:
            lines.append(f"    ? {c.name} ({c.confidence}%) - {c.reason}")

    if skipped:
        lines.append(f"\n  🚫 SKIPPED FOLDERS ({len(skipped)}) - Full list:")
        # Show ALL skipped folders so user can verify
        for c in skipped:
            lines.append(f"    ✗ {c.name} - {c.reason}")

    lines.append("=" * 70 + "\n")

    return "\n".join(lines)

