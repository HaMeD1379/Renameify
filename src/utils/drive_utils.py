"""
Drive utilities module - handles local and network drive enumeration and validation.
"""
import os
import string
import ctypes
from typing import List, Tuple


def get_local_drives() -> List[Tuple[str, str]]:
    """
    Get list of available local drives on Windows.

    Returns:
        List of tuples (drive_letter, drive_label)
    """
    drives = []

    if os.name == 'nt':
        # Windows - use ctypes to get drive info
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_path = f"{letter}:\\"
                try:
                    # Check if drive is ready
                    if os.path.exists(drive_path):
                        # Try to get volume label
                        label = get_drive_label(drive_path)
                        drives.append((drive_path, label))
                except:
                    pass
            bitmask >>= 1

    return drives


def get_drive_label(drive_path: str) -> str:
    """Get the volume label of a drive."""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            volume_name_buffer = ctypes.create_unicode_buffer(1024)
            file_system_buffer = ctypes.create_unicode_buffer(1024)
            serial_number = ctypes.c_ulong()
            max_component_length = ctypes.c_ulong()
            file_system_flags = ctypes.c_ulong()

            result = kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_path),
                volume_name_buffer,
                ctypes.sizeof(volume_name_buffer),
                ctypes.byref(serial_number),
                ctypes.byref(max_component_length),
                ctypes.byref(file_system_flags),
                file_system_buffer,
                ctypes.sizeof(file_system_buffer)
            )

            if result:
                return volume_name_buffer.value or "Local Disk"
        except:
            pass

    return "Local Disk"


def validate_path(path: str) -> Tuple[bool, str]:
    """
    Validate a path (local or network).

    Args:
        path: Path to validate (can be local like D:\\ or UNC like \\\\server\\share)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    # Normalize path
    path = path.strip()

    # Check for UNC path
    if path.startswith("\\\\"):
        return validate_unc_path(path)

    # Check for local path
    return validate_local_path(path)


def validate_unc_path(path: str) -> Tuple[bool, str]:
    """
    Validate a UNC network path.

    Args:
        path: UNC path like \\\\server\\share

    Returns:
        Tuple of (is_valid, error_message)
    """
    path = path.strip()

    # Basic UNC format check
    if not path.startswith("\\\\"):
        return False, "UNC path must start with \\\\"

    # Parse UNC path
    parts = path.replace("\\\\", "").split("\\")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return False, "Invalid UNC path format. Expected: \\\\server\\share"

    server = parts[0]
    share = parts[1]

    # Try to access the path
    try:
        if os.path.exists(path):
            if os.path.isdir(path):
                return True, ""
            else:
                return False, "Path exists but is not a directory"
        else:
            return False, f"Cannot access network path: {path}\nMake sure the network share is accessible and you have permissions."
    except PermissionError:
        return False, f"Permission denied accessing: {path}"
    except Exception as e:
        return False, f"Error accessing path: {str(e)}"


def validate_local_path(path: str) -> Tuple[bool, str]:
    """
    Validate a local path.

    Returns:
        Tuple of (is_valid, error_message)
    """
    path = path.strip()

    try:
        # Normalize and make absolute
        path = os.path.abspath(path)

        if os.path.exists(path):
            if os.path.isdir(path):
                return True, ""
            else:
                return False, "Path exists but is not a directory"
        else:
            return False, f"Directory does not exist: {path}"
    except Exception as e:
        return False, f"Invalid path: {str(e)}"


def normalize_path(path: str) -> str:
    """
    Normalize a path for use with the scanner.
    Handles both local and UNC paths.
    """
    path = path.strip()

    # For UNC paths, ensure proper formatting
    if path.startswith("\\\\"):
        # Use raw path for UNC
        return path

    # For local paths, make absolute
    return os.path.abspath(path)


def test_network_connectivity(server: str) -> Tuple[bool, str]:
    """
    Test if a server is reachable.

    Args:
        server: Server name or IP

    Returns:
        Tuple of (is_reachable, message)
    """
    import subprocess
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "2000", server],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, f"Server {server} is reachable"
        else:
            return False, f"Server {server} is not responding"
    except subprocess.TimeoutExpired:
        return False, f"Connection to {server} timed out"
    except Exception as e:
        return False, f"Error testing connectivity: {str(e)}"


def list_network_shares(server: str) -> List[str]:
    """
    List available shares on a network server.

    Args:
        server: Server name or IP

    Returns:
        List of share names
    """
    shares = []

    try:
        import subprocess
        result = subprocess.run(
            ["net", "view", f"\\\\{server}"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            lines = result.stdout.split("\n")
            for line in lines:
                # Parse share names from net view output
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("Share") and not line.startswith("The command"):
                    parts = line.split()
                    if parts:
                        share_name = parts[0]
                        if share_name and not share_name.endswith("$"):  # Skip admin shares
                            shares.append(share_name)
    except:
        pass

    return shares


def format_drives_list(drives: List[Tuple[str, str]]) -> str:
    """Format list of drives for display."""
    if not drives:
        return "  No drives found."

    lines = []
    for i, (path, label) in enumerate(drives, 1):
        lines.append(f"  [{i}] {path} - {label}")

    return "\n".join(lines)


def get_recent_paths(config: dict) -> List[str]:
    """Get list of recently used paths from config."""
    return config.get("recent_paths", [])


def add_recent_path(path: str, config: dict) -> List[str]:
    """Add a path to recent paths list."""
    recent = config.get("recent_paths", [])

    # Normalize path
    path = normalize_path(path)

    # Remove if already exists
    if path in recent:
        recent.remove(path)

    # Add to front
    recent.insert(0, path)

    # Keep only last 10
    recent = recent[:10]

    config["recent_paths"] = recent
    return recent

