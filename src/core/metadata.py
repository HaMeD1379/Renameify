"""
Metadata module for Renameify - handles reading and writing file metadata.

Supports:
- Video files: MP4, MKV, AVI, MOV, etc. (using mutagen, ffprobe fallback)
- Audio files: MP3, FLAC, WAV, AAC, etc. (using mutagen)

Features:
- Read existing metadata
- Suggest metadata updates based on AI analysis
- Write metadata with user approval
"""
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

# Try importing mutagen for audio/video metadata
try:
    import mutagen
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    from mutagen.wave import WAVE
    from mutagen.aiff import AIFF
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TCON, TPE2, COMM
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


@dataclass
class FileMetadata:
    """Container for file metadata."""
    file_path: str
    file_type: str  # "video", "audio", "unknown"

    # Common metadata
    title: Optional[str] = None
    artist: Optional[str] = None  # For audio, or director for video
    album: Optional[str] = None  # For audio, or series name for TV
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    comment: Optional[str] = None

    # Video-specific
    show_name: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None

    # Audio-specific
    album_artist: Optional[str] = None
    composer: Optional[str] = None
    duration_seconds: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None

    # Technical info
    codec: Optional[str] = None
    container: Optional[str] = None

    # Raw metadata dict for anything else
    raw: Dict[str, Any] = field(default_factory=dict)

    # Status
    has_metadata: bool = False
    is_readable: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def get_display_dict(self) -> dict:
        """Get a clean dict for display, excluding None values and technical fields."""
        result = {}
        display_fields = [
            ("Title", self.title),
            ("Artist", self.artist),
            ("Album", self.album),
            ("Album Artist", self.album_artist),
            ("Year", self.year),
            ("Genre", self.genre),
            ("Track", f"{self.track_number}/{self.total_tracks}" if self.total_tracks else self.track_number),
            ("Show", self.show_name),
            ("Season", self.season),
            ("Episode", self.episode),
            ("Episode Title", self.episode_title),
            ("Duration", f"{int(self.duration_seconds // 60)}:{int(self.duration_seconds % 60):02d}" if self.duration_seconds else None),
            ("Bitrate", f"{self.bitrate // 1000}kbps" if self.bitrate else None),
        ]
        for name, value in display_fields:
            if value is not None:
                result[name] = value
        return result


@dataclass
class MetadataUpdate:
    """Suggested metadata update."""
    file_path: str
    field: str
    current_value: Optional[str]
    suggested_value: str
    confidence: int
    reason: str
    approved: bool = False


def get_file_type(file_path: str) -> str:
    """Determine if file is video or audio based on extension."""
    ext = Path(file_path).suffix.lower()

    video_exts = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.ts', '.m2ts', '.vob',
        '.divx', '.xvid', '.asf', '.rm', '.rmvb', '.ogv'
    }

    audio_exts = {
        '.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg', '.opus',
        '.wma', '.alac', '.aiff', '.ape', '.dsd', '.dsf', '.dff',
        '.mpc', '.tak', '.tta', '.wv', '.ac3', '.dts'
    }

    if ext in video_exts:
        return "video"
    elif ext in audio_exts:
        return "audio"
    return "unknown"


def read_metadata(file_path: str) -> FileMetadata:
    """
    Read metadata from a file.
    Supports video and audio files.
    """
    file_type = get_file_type(file_path)
    metadata = FileMetadata(file_path=file_path, file_type=file_type)

    if not os.path.exists(file_path):
        metadata.is_readable = False
        metadata.error = "File not found"
        return metadata

    try:
        if file_type == "audio":
            metadata = _read_audio_metadata(file_path, metadata)
        elif file_type == "video":
            metadata = _read_video_metadata(file_path, metadata)
    except Exception as e:
        metadata.error = str(e)
        metadata.is_readable = False

    return metadata


def _read_audio_metadata(file_path: str, metadata: FileMetadata) -> FileMetadata:
    """Read metadata from audio file using mutagen."""
    if not MUTAGEN_AVAILABLE:
        metadata.error = "Mutagen library not installed"
        return metadata

    ext = Path(file_path).suffix.lower()

    try:
        audio = mutagen.File(file_path, easy=True)
        if audio is None:
            metadata.error = "Could not read audio file"
            return metadata

        metadata.has_metadata = True
        metadata.duration_seconds = audio.info.length if hasattr(audio.info, 'length') else None
        metadata.bitrate = getattr(audio.info, 'bitrate', None)
        metadata.sample_rate = getattr(audio.info, 'sample_rate', None)
        metadata.channels = getattr(audio.info, 'channels', None)

        # Read common tags
        if audio.tags:
            metadata.title = _get_first(audio.tags.get('title'))
            metadata.artist = _get_first(audio.tags.get('artist'))
            metadata.album = _get_first(audio.tags.get('album'))
            metadata.album_artist = _get_first(audio.tags.get('albumartist'))
            metadata.genre = _get_first(audio.tags.get('genre'))
            metadata.composer = _get_first(audio.tags.get('composer'))

            # Year
            date = _get_first(audio.tags.get('date') or audio.tags.get('year'))
            if date:
                try:
                    metadata.year = int(str(date)[:4])
                except (ValueError, TypeError):
                    pass

            # Track number
            track = _get_first(audio.tags.get('tracknumber'))
            if track:
                if '/' in str(track):
                    parts = str(track).split('/')
                    metadata.track_number = int(parts[0])
                    metadata.total_tracks = int(parts[1]) if len(parts) > 1 else None
                else:
                    try:
                        metadata.track_number = int(track)
                    except (ValueError, TypeError):
                        pass

            # Store raw tags
            metadata.raw = {str(k): str(v) for k, v in audio.tags.items()}

    except Exception as e:
        metadata.error = str(e)

    return metadata


def _read_video_metadata(file_path: str, metadata: FileMetadata) -> FileMetadata:
    """Read metadata from video file."""
    ext = Path(file_path).suffix.lower()

    # Try mutagen for MP4/M4V
    if ext in ['.mp4', '.m4v', '.m4a'] and MUTAGEN_AVAILABLE:
        try:
            video = MP4(file_path)
            metadata.has_metadata = True
            metadata.duration_seconds = video.info.length if hasattr(video.info, 'length') else None
            metadata.bitrate = getattr(video.info, 'bitrate', None)

            if video.tags:
                metadata.title = _get_first(video.tags.get('\xa9nam'))
                metadata.artist = _get_first(video.tags.get('\xa9ART'))
                metadata.album = _get_first(video.tags.get('\xa9alb'))
                metadata.genre = _get_first(video.tags.get('\xa9gen'))
                metadata.comment = _get_first(video.tags.get('\xa9cmt'))

                # Year
                date = _get_first(video.tags.get('\xa9day'))
                if date:
                    try:
                        metadata.year = int(str(date)[:4])
                    except (ValueError, TypeError):
                        pass

                # TV Show metadata
                metadata.show_name = _get_first(video.tags.get('tvsh'))
                season = _get_first(video.tags.get('tvsn'))
                episode = _get_first(video.tags.get('tves'))
                if season:
                    try:
                        metadata.season = int(season)
                    except (ValueError, TypeError):
                        pass
                if episode:
                    try:
                        metadata.episode = int(episode)
                    except (ValueError, TypeError):
                        pass

                metadata.raw = {str(k): str(v) for k, v in video.tags.items()}

            return metadata
        except Exception:
            pass

    # Try ffprobe for other formats
    metadata = _read_metadata_ffprobe(file_path, metadata)
    return metadata


def _read_metadata_ffprobe(file_path: str, metadata: FileMetadata) -> FileMetadata:
    """Read metadata using ffprobe (fallback)."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Get format info
            fmt = data.get('format', {})
            tags = fmt.get('tags', {})

            metadata.has_metadata = bool(tags)
            metadata.duration_seconds = float(fmt.get('duration', 0)) or None
            metadata.bitrate = int(fmt.get('bit_rate', 0)) or None
            metadata.container = fmt.get('format_name')

            # Common tags (case-insensitive)
            tags_lower = {k.lower(): v for k, v in tags.items()}
            metadata.title = tags_lower.get('title')
            metadata.artist = tags_lower.get('artist') or tags_lower.get('author')
            metadata.album = tags_lower.get('album')
            metadata.genre = tags_lower.get('genre')
            metadata.comment = tags_lower.get('comment')

            # Year
            date = tags_lower.get('date') or tags_lower.get('year')
            if date:
                try:
                    metadata.year = int(str(date)[:4])
                except (ValueError, TypeError):
                    pass

            # TV Show
            metadata.show_name = tags_lower.get('show') or tags_lower.get('series')
            season = tags_lower.get('season_number') or tags_lower.get('season')
            episode = tags_lower.get('episode_sort') or tags_lower.get('episode')
            if season:
                try:
                    metadata.season = int(season)
                except (ValueError, TypeError):
                    pass
            if episode:
                try:
                    metadata.episode = int(episode)
                except (ValueError, TypeError):
                    pass

            # Get codec from streams
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    metadata.codec = stream.get('codec_name')
                    break
                elif stream.get('codec_type') == 'audio' and not metadata.codec:
                    metadata.codec = stream.get('codec_name')

            metadata.raw = tags

    except FileNotFoundError:
        # ffprobe not available
        pass
    except subprocess.TimeoutExpired:
        metadata.error = "Timeout reading metadata"
    except Exception as e:
        metadata.error = str(e)

    return metadata


def _get_first(value) -> Optional[str]:
    """Get first value from a list or return the value itself."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) > 0:
        return str(value[0])
    return str(value) if value else None


def write_metadata(file_path: str, updates: Dict[str, Any]) -> bool:
    """
    Write metadata to a file.

    Args:
        file_path: Path to the file
        updates: Dict of field names to values

    Returns:
        True if successful, False otherwise
    """
    if not MUTAGEN_AVAILABLE:
        return False

    file_type = get_file_type(file_path)

    try:
        if file_type == "audio":
            return _write_audio_metadata(file_path, updates)
        elif file_type == "video":
            return _write_video_metadata(file_path, updates)
    except Exception:
        return False

    return False


def _write_audio_metadata(file_path: str, updates: Dict[str, Any]) -> bool:
    """Write metadata to audio file."""
    ext = Path(file_path).suffix.lower()

    try:
        if ext == '.mp3':
            audio = MP3(file_path)
            if audio.tags is None:
                audio.add_tags()

            tag_map = {
                'title': lambda v: TIT2(encoding=3, text=v),
                'artist': lambda v: TPE1(encoding=3, text=v),
                'album': lambda v: TALB(encoding=3, text=v),
                'album_artist': lambda v: TPE2(encoding=3, text=v),
                'year': lambda v: TDRC(encoding=3, text=str(v)),
                'track_number': lambda v: TRCK(encoding=3, text=str(v)),
                'genre': lambda v: TCON(encoding=3, text=v),
                'comment': lambda v: COMM(encoding=3, text=v, lang='eng', desc=''),
            }

            for field, value in updates.items():
                if field in tag_map and value is not None:
                    frame = tag_map[field](value)
                    audio.tags.add(frame)

            audio.save()
            return True

        else:
            # Use EasyID3 style for other formats
            audio = mutagen.File(file_path, easy=True)
            if audio is None:
                return False

            field_map = {
                'title': 'title',
                'artist': 'artist',
                'album': 'album',
                'album_artist': 'albumartist',
                'year': 'date',
                'track_number': 'tracknumber',
                'genre': 'genre',
            }

            for field, value in updates.items():
                if field in field_map and value is not None:
                    audio[field_map[field]] = str(value)

            audio.save()
            return True

    except Exception:
        return False


def _write_video_metadata(file_path: str, updates: Dict[str, Any]) -> bool:
    """Write metadata to video file (MP4/M4V only for now)."""
    ext = Path(file_path).suffix.lower()

    if ext not in ['.mp4', '.m4v'] or not MUTAGEN_AVAILABLE:
        return False

    try:
        video = MP4(file_path)
        if video.tags is None:
            video.add_tags()

        tag_map = {
            'title': '\xa9nam',
            'artist': '\xa9ART',
            'album': '\xa9alb',
            'year': '\xa9day',
            'genre': '\xa9gen',
            'comment': '\xa9cmt',
            'show_name': 'tvsh',
            'season': 'tvsn',
            'episode': 'tves',
        }

        for field, value in updates.items():
            if field in tag_map and value is not None:
                tag = tag_map[field]
                if field in ['season', 'episode']:
                    video.tags[tag] = [int(value)]
                else:
                    video.tags[tag] = [str(value)]

        video.save()
        return True

    except Exception:
        return False


def generate_metadata_suggestions(
    file_path: str,
    ai_info: Dict[str, Any],
    current_metadata: FileMetadata
) -> List[MetadataUpdate]:
    """
    Generate metadata update suggestions based on AI analysis.

    Args:
        file_path: Path to the file
        ai_info: Dict containing AI-analyzed information (title, year, etc.)
        current_metadata: Current metadata from the file

    Returns:
        List of MetadataUpdate suggestions
    """
    suggestions = []

    # Map AI info fields to metadata fields
    field_mappings = [
        ('title', 'title', 'AI identified title'),
        ('year', 'year', 'AI identified year'),
        ('artist', 'artist', 'AI identified artist'),
        ('album', 'album', 'AI identified album'),
        ('show_name', 'show_name', 'AI identified show name'),
        ('season', 'season', 'AI identified season'),
        ('episode', 'episode', 'AI identified episode'),
        ('episode_title', 'episode_title', 'AI identified episode title'),
    ]

    for ai_field, meta_field, reason in field_mappings:
        ai_value = ai_info.get(ai_field)
        current_value = getattr(current_metadata, meta_field, None)

        if ai_value and str(ai_value) != str(current_value):
            confidence = ai_info.get('confidence', 80)

            suggestions.append(MetadataUpdate(
                file_path=file_path,
                field=meta_field,
                current_value=str(current_value) if current_value else None,
                suggested_value=str(ai_value),
                confidence=confidence,
                reason=reason
            ))

    return suggestions


def batch_read_metadata(file_paths: List[str]) -> Dict[str, FileMetadata]:
    """
    Read metadata from multiple files.

    Args:
        file_paths: List of file paths

    Returns:
        Dict mapping file paths to their metadata
    """
    results = {}
    for path in file_paths:
        results[path] = read_metadata(path)
    return results


def is_mutagen_available() -> bool:
    """Check if mutagen library is available."""
    return MUTAGEN_AVAILABLE
