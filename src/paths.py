"""Path resolution for development and PyInstaller-frozen modes.

Read-only resources (dictionary JSONs) are bundled into the exe and
accessed via sys._MEIPASS when frozen.

Writable user data (collections.json, srs_data.json) lives in a data/
directory next to the executable.
"""

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_dir() -> Path:
    """Read-only directory for bundled dictionary data files."""
    if _is_frozen():
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parent.parent / "data"


def user_data_dir() -> Path:
    """Writable directory for collections, SRS state, etc."""
    if _is_frozen():
        # Next to the .exe
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent.parent / "data"
