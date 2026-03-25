"""
Rollback module - handles saving and restoring rename operations.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from .config import load_config, get_logs_dir as get_config_logs_dir


@dataclass
class RenameOperation:
    """Single rename operation record."""
    original_path: str
    new_path: str
    media_type: str
    confidence: int
    timestamp: str


@dataclass
class RenameManifest:
    """Complete manifest for a batch rename operation."""
    id: str
    timestamp: str
    root_path: str
    total_operations: int
    operations: List[Dict]
    applied: bool
    rolled_back: bool
    folder_renames: List[Dict] = None  # Parent folder rename operations

    def __post_init__(self):
        if self.folder_renames is None:
            self.folder_renames = []


def get_logs_dir(config: Optional[dict] = None) -> Path:
    """Get the logs directory path."""
    if config is None:
        config = load_config()

    logs_dir = Path(config.get("logs_dir", "rename_logs"))
    if not logs_dir.is_absolute():
        logs_dir = Path(__file__).parent / logs_dir

    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def generate_manifest_id() -> str:
    """Generate a unique manifest ID based on timestamp."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_manifest(manifest: RenameManifest, config: Optional[dict] = None) -> Path:
    """Save a rename manifest to disk."""
    logs_dir = get_logs_dir(config)
    manifest_file = logs_dir / f"{manifest.id}_rename_manifest.json"

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)

    return manifest_file


def load_manifest(manifest_id: str, config: Optional[dict] = None) -> Optional[RenameManifest]:
    """Load a rename manifest from disk."""
    logs_dir = get_logs_dir(config)
    manifest_file = logs_dir / f"{manifest_id}_rename_manifest.json"

    if not manifest_file.exists():
        return None

    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return RenameManifest(
        id=data["id"],
        timestamp=data["timestamp"],
        root_path=data["root_path"],
        total_operations=data["total_operations"],
        operations=data["operations"],
        applied=data["applied"],
        rolled_back=data["rolled_back"],
        folder_renames=data.get("folder_renames", [])
    )


def update_manifest_status(manifest_id: str, applied: bool = None, rolled_back: bool = None, config: Optional[dict] = None) -> None:
    """Update the status of a manifest."""
    manifest = load_manifest(manifest_id, config)
    if manifest:
        if applied is not None:
            manifest.applied = applied
        if rolled_back is not None:
            manifest.rolled_back = rolled_back
        save_manifest(manifest, config)


def list_manifests(config: Optional[dict] = None) -> List[RenameManifest]:
    """List all available manifests."""
    logs_dir = get_logs_dir(config)
    manifests = []

    for f in sorted(logs_dir.glob("*_rename_manifest.json"), reverse=True):
        manifest_id = f.stem.replace("_rename_manifest", "")
        manifest = load_manifest(manifest_id, config)
        if manifest:
            manifests.append(manifest)

    return manifests


def get_latest_manifest(config: Optional[dict] = None) -> Optional[RenameManifest]:
    """Get the most recent manifest."""
    manifests = list_manifests(config)
    return manifests[0] if manifests else None


def create_manifest_from_plan(rename_plan: List[Dict], root_path: str, folder_renames: List[Dict] = None) -> RenameManifest:
    """Create a manifest from a rename plan."""
    manifest_id = generate_manifest_id()

    operations = []
    for item in rename_plan:
        op = {
            "original_path": str(item["original_path"]),
            "new_path": str(item["new_path"]),
            "media_type": item.get("media_type", "unknown"),
            "confidence": item.get("confidence", 0),
            "title": item.get("title", "Unknown")
        }
        operations.append(op)

    manifest = RenameManifest(
        id=manifest_id,
        timestamp=datetime.now().isoformat(),
        root_path=root_path,
        total_operations=len(operations),
        operations=operations,
        applied=False,
        rolled_back=False,
        folder_renames=folder_renames or []
    )

    return manifest


def format_manifest_summary(manifest: RenameManifest) -> str:
    """Format manifest for display."""
    status = "Not Applied"
    if manifest.rolled_back:
        status = "Rolled Back"
    elif manifest.applied:
        status = "Applied"

    lines = [
        f"\n{'='*60}",
        f"  Manifest: {manifest.id}",
        f"{'='*60}",
        f"  Timestamp:   {manifest.timestamp}",
        f"  Root Path:   {manifest.root_path}",
        f"  Operations:  {manifest.total_operations}",
        f"  Status:      {status}",
        f"{'='*60}\n"
    ]

    return "\n".join(lines)


def format_manifests_list(manifests: List[RenameManifest]) -> str:
    """Format list of manifests for display."""
    if not manifests:
        return "\nNo rename manifests found.\n"

    lines = [
        f"\n{'='*70}",
        f"  RENAME HISTORY",
        f"{'='*70}",
        f"  {'ID':<20} {'Date':<20} {'Files':<10} {'Status':<15}",
        f"  {'-'*65}"
    ]

    for m in manifests:
        status = "Rolled Back" if m.rolled_back else ("Applied" if m.applied else "Pending")
        date_str = m.timestamp[:19].replace("T", " ")
        lines.append(f"  {m.id:<20} {date_str:<20} {m.total_operations:<10} {status:<15}")

    lines.append(f"{'='*70}\n")

    return "\n".join(lines)

