"""
core/app_icon.py — Application icon resolution and QIcon loader.

Provides robust icon resolution for ProAssist AI across:
- Normal development runtime (any working directory)
- Frozen PyInstaller bundles (one-file via sys._MEIPASS and one-dir)
- Fallback paths (ICO -> PNG -> empty QIcon)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtGui import QIcon


def get_project_root() -> Path:
    """
    Resolve the project root directory safely whether running as source or frozen.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_app_icon_ico_path() -> Path | None:
    """Return the absolute path to proassist_icon.ico if it exists, else None."""
    root = get_project_root()
    p = root / "assets" / "proassist_icon.ico"
    return p if p.is_file() else None


def get_app_icon_png_path() -> Path | None:
    """Return the absolute path to proassist_icon.png if it exists, else None."""
    root = get_project_root()
    p = root / "assets" / "proassist_icon.png"
    return p if p.is_file() else None


def get_app_icon_path() -> Path | None:
    """
    Return path to the best available icon file:
    Prefers assets/proassist_icon.ico, falls back to assets/proassist_icon.png,
    or None if neither exists.
    """
    ico = get_app_icon_ico_path()
    if ico is not None:
        return ico
    return get_app_icon_png_path()


def get_app_icon() -> "QIcon":
    """
    Build a QIcon from assets/proassist_icon.ico, falling back to the PNG,
    and returning an empty QIcon without crashing if neither exists.
    """
    try:
        from PyQt6.QtGui import QIcon
    except ImportError:
        # If PyQt6 is not installed or importable, return dummy / None safely
        return None  # type: ignore[return-value]

    try:
        ico_path = get_app_icon_ico_path()
        if ico_path is not None:
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon

        png_path = get_app_icon_png_path()
        if png_path is not None:
            icon = QIcon(str(png_path))
            if not icon.isNull():
                return icon

        return QIcon()
    except Exception:
        try:
            return QIcon()
        except Exception:
            return None  # type: ignore[return-value]
