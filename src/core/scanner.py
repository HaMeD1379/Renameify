"""
File scanner module - recursively scans directories for media files.
"""
import os
import re
import fnmatch
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict

from .config import load_config


@dataclass
class SubtitleFile:
    """Represents a subtitle file."""
    path: Path
    filename: str
    extension: str
    language: Optional[str] = None  # e.g., "en", "es", "fa"

    def __str__(self):
        return str(self.path)


@dataclass
class MediaFile:
    """Represents a media file found during scanning."""
    path: Path
    filename: str
    extension: str
    parent_folder: str
    size_mb: float
    subtitles: List[SubtitleFile] = field(default_factory=list)  # Associated subtitles

    def __str__(self):
        return str(self.path)


@dataclass
class ScanProgress:
    """Progress information during scanning."""
    folders_scanned: int
    files_found: int
    subtitles_found: int
    current_folder: str
    skipped_folders: int
    elapsed_seconds: float
    phase: str = "scanning"  # "filtering", "scanning", "complete"


# BDMV/Blu-ray folder markers - don't descend into these
BDMV_INTERNAL_FOLDERS = {'bdmv', 'certificate', 'backup', 'playlist', 'clipinf', 'stream', 'auxdata', 'meta', 'jar'}


def is_bdmv_internal_folder(folder_name: str) -> bool:
    """Check if folder is part of BDMV internal structure."""
    return folder_name.lower() in BDMV_INTERNAL_FOLDERS


def is_excluded(path: Path, config: dict) -> bool:
    """Check if a path should be excluded from scanning."""
    path_str = str(path).lower()

    # Check excluded paths
    for excluded in config.get("excluded_paths", []):
        excluded_lower = excluded.lower()
        if excluded_lower in path_str or fnmatch.fnmatch(path_str, excluded_lower):
            return True

    # Check excluded folder names
    for folder_name in config.get("excluded_folder_names", []):
        if folder_name.lower() in path_str.lower().split(os.sep):
            return True

    return False


def has_ignore_file(folder: Path) -> bool:
    """Check if folder contains a .renamer-ignore file."""
    ignore_file = folder / ".renamer-ignore"
    return ignore_file.exists()


def is_bdmv_root(folder: Path) -> bool:
    """Check if folder is the root of a BDMV structure (contains BDMV subfolder)."""
    try:
        for item in folder.iterdir():
            if item.is_dir() and item.name.lower() == 'bdmv':
                return True
        return False
    except (PermissionError, OSError):
        return False


def scan_directory(
    root_path: str,
    config: Optional[dict] = None,
    progress_callback: Optional[Callable[[ScanProgress], None]] = None,
    folders_to_scan: Optional[List[str]] = None
) -> List[MediaFile]:
    """
    Recursively scan a directory for media files and their subtitles.
    Supports both local paths and UNC network paths.

    Args:
        root_path: The root directory to scan (can be local or UNC path)
        config: Optional config dict (loads from file if not provided)
        progress_callback: Optional callback function called with progress updates
        folders_to_scan: Optional list of specific folders to scan (for smart filtering)

    Returns:
        List of MediaFile objects found (with associated subtitles)
    """
    if config is None:
        config = load_config()

    # Handle UNC paths properly
    root_path = root_path.strip()

    # For UNC paths, use as-is; for local paths, use Path normalization
    if root_path.startswith("\\\\"):
        root = Path(root_path)
    else:
        root = Path(root_path)

    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")

    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_path}")

    video_extensions = set(ext.lower() for ext in config.get("video_extensions", []))
    subtitle_extensions = set(ext.lower() for ext in config.get("subtitle_extensions", []))

    media_files = []
    subtitle_files_found = []  # Track subtitles separately for matching
    skipped_folders = []
    folders_scanned = 0
    subtitles_count = 0
    start_time = time.time()
    last_update = 0

    # Determine which directories to walk
    if folders_to_scan:
        # Smart filtered mode - only scan specified folders
        dirs_to_walk = folders_to_scan
    else:
        # Full scan mode
        dirs_to_walk = [str(root)]

    for scan_root in dirs_to_walk:
        for dirpath, dirnames, filenames in os.walk(scan_root):
            current_dir = Path(dirpath)
            folders_scanned += 1

            # Send progress update every 0.1 seconds to avoid slowdown
            current_time = time.time()
            if progress_callback and (current_time - last_update) >= 0.1:
                last_update = current_time
                progress = ScanProgress(
                    folders_scanned=folders_scanned,
                    files_found=len(media_files),
                    subtitles_found=subtitles_count,
                    current_folder=str(current_dir),  # Full path - display layer handles truncation
                    skipped_folders=len(skipped_folders),
                    elapsed_seconds=current_time - start_time,
                    phase="scanning"
                )
                progress_callback(progress)

            # Check for .renamer-ignore file
            if has_ignore_file(current_dir):
                skipped_folders.append(str(current_dir))
                dirnames.clear()
                continue

            # Check if current path is excluded
            if is_excluded(current_dir, config):
                skipped_folders.append(str(current_dir))
                dirnames.clear()
                continue

            # Check if we're inside a BDMV structure - skip internal folders
            if is_bdmv_internal_folder(current_dir.name):
                skipped_folders.append(str(current_dir))
                dirnames.clear()  # Don't descend further
                continue

            # Filter out excluded subdirectories and BDMV internal folders
            dirnames[:] = [
                d for d in dirnames
                if not is_excluded(current_dir / d, config)
                and not has_ignore_file(current_dir / d)
                and not is_bdmv_internal_folder(d)  # Skip BDMV internal folders
            ]

            # Collect all video and subtitle files in this directory
            dir_videos = []
            dir_subtitles = []

            for filename in filenames:
                file_path = current_dir / filename
                extension = file_path.suffix.lower()

                if extension in video_extensions:
                    try:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                    except OSError:
                        size_mb = 0

                    media_file = MediaFile(
                        path=file_path,
                        filename=file_path.stem,
                        extension=extension,
                        parent_folder=current_dir.name,
                        size_mb=round(size_mb, 2),
                        subtitles=[]
                    )
                    dir_videos.append(media_file)

                elif extension in subtitle_extensions:
                    # Parse language from subtitle filename if present
                    lang = extract_subtitle_language(file_path.stem)
                    subtitle = SubtitleFile(
                        path=file_path,
                        filename=file_path.stem,
                        extension=extension,
                        language=lang
                    )
                    dir_subtitles.append(subtitle)
                    subtitles_count += 1

            # Match subtitles to videos in same directory
            for video in dir_videos:
                video.subtitles = find_matching_subtitles(video, dir_subtitles)
                media_files.append(video)

            # Also check for subtitles in "Subs" or "Subtitles" subdirectories
            for subdir_name in ["Subs", "subs", "Subtitles", "subtitles", "Sub"]:
                subs_dir = current_dir / subdir_name
                if subs_dir.exists() and subs_dir.is_dir():
                    for sub_file in subs_dir.iterdir():
                        if sub_file.suffix.lower() in subtitle_extensions:
                            lang = extract_subtitle_language(sub_file.stem)
                            subtitle = SubtitleFile(
                                path=sub_file,
                                filename=sub_file.stem,
                                extension=sub_file.suffix.lower(),
                                language=lang
                            )
                            subtitles_count += 1
                            # Try to match with videos in parent directory
                            for video in dir_videos:
                                if is_subtitle_match(video, subtitle):
                                    if subtitle not in video.subtitles:
                                        video.subtitles.append(subtitle)

    # Final progress update
    if progress_callback:
        progress = ScanProgress(
            folders_scanned=folders_scanned,
            files_found=len(media_files),
            subtitles_found=subtitles_count,
            current_folder="Complete",
            skipped_folders=len(skipped_folders),
            elapsed_seconds=time.time() - start_time,
            phase="complete"
        )
        progress_callback(progress)

    return media_files


def extract_subtitle_language(filename: str) -> Optional[str]:
    """
    Extract language code from subtitle filename.
    Common patterns: movie.en.srt, movie.english.srt, movie_eng.srt
    """
    filename_lower = filename.lower()

    # Common language codes and names
    lang_patterns = {
        'english': 'en', 'eng': 'en', 'en': 'en',
        'persian': 'fa', 'farsi': 'fa', 'fa': 'fa', 'per': 'fa',
        'spanish': 'es', 'esp': 'es', 'es': 'es',
        'french': 'fr', 'fra': 'fr', 'fr': 'fr',
        'german': 'de', 'ger': 'de', 'de': 'de', 'deu': 'de',
        'arabic': 'ar', 'ara': 'ar', 'ar': 'ar',
        'chinese': 'zh', 'chi': 'zh', 'zh': 'zh', 'chs': 'zh', 'cht': 'zh',
        'japanese': 'ja', 'jpn': 'ja', 'ja': 'ja',
        'korean': 'ko', 'kor': 'ko', 'ko': 'ko',
        'italian': 'it', 'ita': 'it', 'it': 'it',
        'portuguese': 'pt', 'por': 'pt', 'pt': 'pt',
        'russian': 'ru', 'rus': 'ru', 'ru': 'ru',
        'turkish': 'tr', 'tur': 'tr', 'tr': 'tr',
        'dutch': 'nl', 'dut': 'nl', 'nl': 'nl',
        'polish': 'pl', 'pol': 'pl', 'pl': 'pl',
        'swedish': 'sv', 'swe': 'sv', 'sv': 'sv',
        'hebrew': 'he', 'heb': 'he', 'he': 'he',
        'hindi': 'hi', 'hin': 'hi', 'hi': 'hi',
    }

    # Check for language at end of filename (most common)
    # Pattern: name.lang or name_lang or name-lang
    parts = re.split(r'[._\-\s]', filename_lower)
    for part in reversed(parts[-3:]):  # Check last 3 parts
        if part in lang_patterns:
            return lang_patterns[part]

    return None


def find_matching_subtitles(video: MediaFile, subtitles: List[SubtitleFile]) -> List[SubtitleFile]:
    """Find subtitles that match a video file."""
    matches = []
    video_name_lower = video.filename.lower()

    for sub in subtitles:
        if is_subtitle_match(video, sub):
            matches.append(sub)

    return matches


def is_subtitle_match(video: MediaFile, subtitle: SubtitleFile) -> bool:
    """Check if a subtitle file matches a video file."""
    video_name = video.filename.lower()
    sub_name = subtitle.filename.lower()

    # Exact match (minus language suffix)
    if sub_name.startswith(video_name):
        return True

    # Remove common suffixes and compare
    # Strip quality tags, release group, etc. from both
    def normalize_name(name):
        # Remove common tags
        patterns = [
            r'\b(720p|1080p|2160p|4k)\b',
            r'\b(bluray|webrip|web-dl|hdtv|dvdrip|brrip)\b',
            r'\b(x264|x265|hevc|aac|dts|ac3)\b',
            r'\b(proper|repack|internal)\b',
            r'\[.*?\]',  # Brackets
            r'\(.*?\)',  # Parentheses
        ]
        result = name.lower()
        for p in patterns:
            result = re.sub(p, '', result, flags=re.IGNORECASE)
        # Remove extra spaces and dots
        result = re.sub(r'[.\-_\s]+', ' ', result).strip()
        return result

    norm_video = normalize_name(video_name)
    norm_sub = normalize_name(sub_name)

    # Check if one starts with the other
    if norm_sub.startswith(norm_video[:20]) or norm_video.startswith(norm_sub[:20]):
        return True

    # Check for significant overlap (for messy filenames)
    video_words = set(norm_video.split())
    sub_words = set(norm_sub.split())
    if len(video_words) >= 2 and len(sub_words) >= 2:
        overlap = video_words & sub_words
        if len(overlap) >= min(len(video_words), len(sub_words)) * 0.6:
            return True

    return False


def get_scan_summary(media_files: List[MediaFile]) -> dict:
    """Generate a summary of scanned files."""
    total_size = sum(f.size_mb for f in media_files)
    extensions = {}
    total_subtitles = 0
    files_with_subs = 0

    for f in media_files:
        ext = f.extension
        extensions[ext] = extensions.get(ext, 0) + 1
        if f.subtitles:
            total_subtitles += len(f.subtitles)
            files_with_subs += 1

    return {
        "total_files": len(media_files),
        "total_size_gb": round(total_size / 1024, 2),
        "extensions": extensions,
        "total_subtitles": total_subtitles,
        "files_with_subtitles": files_with_subs
    }


def format_scan_results(media_files: List[MediaFile]) -> str:
    """Format scan results for display."""
    if not media_files:
        return "No media files found."

    summary = get_scan_summary(media_files)

    lines = [
        f"\n{'='*60}",
        f"  SCAN RESULTS",
        f"{'='*60}",
        f"  Total video files:    {summary['total_files']}",
        f"  Total size:           {summary['total_size_gb']} GB",
        f"  Subtitles found:      {summary['total_subtitles']}",
        f"  Videos with subs:     {summary['files_with_subtitles']}",
        f"\n  Video extensions found:"
    ]

    for ext, count in sorted(summary['extensions'].items()):
        lines.append(f"    {ext}: {count} files")

    lines.append(f"{'='*60}\n")

    return "\n".join(lines)

