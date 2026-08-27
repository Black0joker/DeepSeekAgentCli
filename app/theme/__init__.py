"""Centralized color theme for the DeepSeek CLI terminal UI.

All widgets should import from this module instead of hardcoding colors.
Supports loading custom themes from config/theme.json.

Usage:
    from app.theme import ACCENT, BG_WIDGET, TEXT_PRIMARY
    from app.theme import load_theme, get_theme
"""
import json
import os
from pathlib import Path
from typing import Optional

from app.agent.logger import Logger


# ── Private state ──────────────────────────────────────────────────────────

_current_theme_name: str = "default"
_custom_overrides: dict = {}


# ── Default palette ───────────────────────────────────────────────────────

# Primary accent (purple) used for commands, diamond symbol, highlights
ACCENT = "#C792EA"
ACCENT_RGB = "rgb(199,146,234)"

# Backgrounds
BG_MAIN = "#000000"       # main app background
BG_WIDGET = "#1A1A1A"      # slightly lighter background for cards / widgets
BG_INPUT = "#292929"       # input box background

# Text
TEXT_PRIMARY = "#FFFFFF"   # primary white text
TEXT_SECONDARY = "#A0A0A0" # gray for footer, status bar
TEXT_MUTED = "#DCDCDC"     # system / meta messages

# Borders
BORDER_LIGHT = "rgba(255,255,255,0.08)"  # subtle borders
BORDER_MEDIUM = "rgba(255,255,255,0.2)"  # visible borders (suggestions, permissions)

# Text RGB (for use with Rich Text objects)
TEXT_PRIMARY_RGB = "rgb(255,255,255)"
TEXT_MUTED_RGB = "rgb(220,220,220)"

# Semantic
SUCCESS = "#00FF00"   # green checkmarks / success
ERROR = "#FF0000"     # red errors
WARNING = "#FFFF00"   # yellow warnings / permission requests

# Logo gradient (light blue → purple)
LOGO_GRADIENT = [
    "rgb(110,168,254)",
    "rgb(125,159,254)",
    "rgb(139,124,255)",
    "rgb(159,124,255)",
    "rgb(178,108,255)",
    "rgb(189,115,255)",
    "rgb(200,122,255)",
]


# ── Built-in presets ──────────────────────────────────────────────────────

PRESETS = {
    "default": {},
    "dracula": {
        "ACCENT": "#BD93F9",
        "ACCENT_RGB": "rgb(189,147,249)",
        "BG_MAIN": "#282A36",
        "BG_WIDGET": "#21222C",
        "BG_INPUT": "#383A59",
        "TEXT_PRIMARY": "#F8F8F2",
        "TEXT_SECONDARY": "#6272A4",
        "TEXT_MUTED": "#BDC3DB",
        "BORDER_LIGHT": "rgba(248,248,242,0.08)",
        "BORDER_MEDIUM": "rgba(248,248,242,0.2)",
        "TEXT_PRIMARY_RGB": "rgb(248,248,242)",
        "TEXT_MUTED_RGB": "rgb(189,195,219)",
        "SUCCESS": "#50FA7B",
        "ERROR": "#FF5555",
        "WARNING": "#F1FA8C",
    },
    "gruvbox": {
        "ACCENT": "#FABD2F",
        "ACCENT_RGB": "rgb(250,189,47)",
        "BG_MAIN": "#282828",
        "BG_WIDGET": "#32302F",
        "BG_INPUT": "#3C3836",
        "TEXT_PRIMARY": "#EBDBB2",
        "TEXT_SECONDARY": "#A89984",
        "TEXT_MUTED": "#D5C4A1",
        "BORDER_LIGHT": "rgba(235,219,178,0.08)",
        "BORDER_MEDIUM": "rgba(235,219,178,0.2)",
        "TEXT_PRIMARY_RGB": "rgb(235,219,178)",
        "TEXT_MUTED_RGB": "rgb(213,196,161)",
        "SUCCESS": "#B8BB26",
        "ERROR": "#FB4934",
        "WARNING": "#FABD2F",
    },
    "nord": {
        "ACCENT": "#88C0D0",
        "ACCENT_RGB": "rgb(136,192,208)",
        "BG_MAIN": "#2E3440",
        "BG_WIDGET": "#3B4252",
        "BG_INPUT": "#434C5E",
        "TEXT_PRIMARY": "#ECEFF4",
        "TEXT_SECONDARY": "#81A1C1",
        "TEXT_MUTED": "#D8DEE9",
        "BORDER_LIGHT": "rgba(236,239,244,0.08)",
        "BORDER_MEDIUM": "rgba(236,239,244,0.2)",
        "TEXT_PRIMARY_RGB": "rgb(236,239,244)",
        "TEXT_MUTED_RGB": "rgb(216,222,233)",
        "SUCCESS": "#A3BE8C",
        "ERROR": "#BF616A",
        "WARNING": "#EBCB8B",
    },
    "monokai": {
        "ACCENT": "#A6E22E",
        "ACCENT_RGB": "rgb(166,226,46)",
        "BG_MAIN": "#272822",
        "BG_WIDGET": "#3E3D32",
        "BG_INPUT": "#49483E",
        "TEXT_PRIMARY": "#F8F8F2",
        "TEXT_SECONDARY": "#75715E",
        "TEXT_MUTED": "#CFCFC2",
        "BORDER_LIGHT": "rgba(248,248,242,0.08)",
        "BORDER_MEDIUM": "rgba(248,248,242,0.2)",
        "TEXT_PRIMARY_RGB": "rgb(248,248,242)",
        "TEXT_MUTED_RGB": "rgb(207,207,194)",
        "SUCCESS": "#A6E22E",
        "ERROR": "#F92672",
        "WARNING": "#E6DB74",
    },
    "solarized_dark": {
        "ACCENT": "#268BD2",
        "ACCENT_RGB": "rgb(38,139,210)",
        "BG_MAIN": "#002B36",
        "BG_WIDGET": "#073642",
        "BG_INPUT": "#0A4E5C",
        "TEXT_PRIMARY": "#FDF6E3",
        "TEXT_SECONDARY": "#839496",
        "TEXT_MUTED": "#EEE8D5",
        "BORDER_LIGHT": "rgba(253,246,227,0.08)",
        "BORDER_MEDIUM": "rgba(253,246,227,0.2)",
        "TEXT_PRIMARY_RGB": "rgb(253,246,227)",
        "TEXT_MUTED_RGB": "rgb(238,232,213)",
        "SUCCESS": "#859900",
        "ERROR": "#DC322F",
        "WARNING": "#B58900",
    },
}


# ── Theme path resolution ─────────────────────────────────────────────────

def _get_config_dir() -> Path:
    """Get the project config directory."""
    import sys
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent.parent.parent
    return base / "config"


# ── Public API ────────────────────────────────────────────────────────────

def get_theme() -> dict:
    """Return the current theme as a dictionary of all color values."""
    return {
        "name": _current_theme_name,
        "ACCENT": ACCENT,
        "ACCENT_RGB": ACCENT_RGB,
        "BG_MAIN": BG_MAIN,
        "BG_WIDGET": BG_WIDGET,
        "BG_INPUT": BG_INPUT,
        "TEXT_PRIMARY": TEXT_PRIMARY,
        "TEXT_SECONDARY": TEXT_SECONDARY,
        "TEXT_MUTED": TEXT_MUTED,
        "BORDER_LIGHT": BORDER_LIGHT,
        "BORDER_MEDIUM": BORDER_MEDIUM,
        "TEXT_PRIMARY_RGB": TEXT_PRIMARY_RGB,
        "TEXT_MUTED_RGB": TEXT_MUTED_RGB,
        "SUCCESS": SUCCESS,
        "ERROR": ERROR,
        "WARNING": WARNING,
        "LOGO_GRADIENT": LOGO_GRADIENT,
    }


def list_presets() -> list:
    """Return list of available preset theme names."""
    return sorted(PRESETS.keys())


def load_theme(theme_name: Optional[str] = None, config_path: Optional[str] = None) -> bool:
    """Load a theme from presets or a JSON config file.

    Order of precedence:
    1. Explicit theme_name matching a built-in preset (when provided)
    2. JSON config file at config_path or config/theme.json
    3. Default theme

    Returns True if a theme was loaded. Returns False when theme_name is
    provided but does not match any built-in preset.
    """
    global _current_theme_name, _custom_overrides
    global ACCENT, ACCENT_RGB, BG_MAIN, BG_WIDGET, BG_INPUT
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
    global BORDER_LIGHT, BORDER_MEDIUM
    global TEXT_PRIMARY_RGB, TEXT_MUTED_RGB
    global SUCCESS, ERROR, WARNING, LOGO_GRADIENT

    overrides = {}

    if theme_name is not None:
        # An explicit preset was requested; it must exist.
        if theme_name not in PRESETS:
            return False
        overrides = dict(PRESETS[theme_name])
        _current_theme_name = theme_name
    else:
        # No explicit theme requested: try the config file, then defaults.
        if config_path:
            path = Path(config_path)
        else:
            path = _get_config_dir() / "theme.json"

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
                _current_theme_name = overrides.pop("_name", path.stem)
            except (json.JSONDecodeError, OSError) as e:
                Logger.warn(f"Failed to load theme config from {path}: {e}")
                overrides = {}

        if not overrides:
            _current_theme_name = "default"
            overrides = {}

    # Apply overrides (only update globals for keys that exist in defaults)
    _custom_overrides = overrides

    _apply_override("ACCENT", overrides)
    _apply_override("ACCENT_RGB", overrides)
    _apply_override("BG_MAIN", overrides)
    _apply_override("BG_WIDGET", overrides)
    _apply_override("BG_INPUT", overrides)
    _apply_override("TEXT_PRIMARY", overrides)
    _apply_override("TEXT_SECONDARY", overrides)
    _apply_override("TEXT_MUTED", overrides)
    _apply_override("BORDER_LIGHT", overrides)
    _apply_override("BORDER_MEDIUM", overrides)
    _apply_override("TEXT_PRIMARY_RGB", overrides)
    _apply_override("TEXT_MUTED_RGB", overrides)
    _apply_override("SUCCESS", overrides)
    _apply_override("ERROR", overrides)
    _apply_override("WARNING", overrides)

    if "LOGO_GRADIENT" in overrides:
        LOGO_GRADIENT = overrides["LOGO_GRADIENT"]

    return True


def _apply_override(key: str, overrides: dict) -> None:
    """Apply a single override to the module global."""
    import sys
    if key in overrides:
        setattr(sys.modules[__name__], key, overrides[key])


def build_textual_theme():
    """Build a ``textual.theme.Theme`` from the current palette.

    The Textual theme drives all CSS variables (``$background``, ``$panel``,
    ``$foreground``, ``$accent``, ``$border-light``, ...). Registering it
    with the App and setting ``App.theme`` to its name reparses the
    stylesheet and restyles the entire UI live.
    """
    from textual.theme import Theme

    return Theme(
        name=f"warriorx-{_current_theme_name}",
        primary=ACCENT,
        secondary=TEXT_SECONDARY,
        warning=WARNING,
        error=ERROR,
        success=SUCCESS,
        accent=ACCENT,
        foreground=TEXT_PRIMARY,
        background=BG_MAIN,
        surface=BG_WIDGET,
        panel=BG_INPUT,
        dark=True,
        variables={
            "text-secondary": TEXT_SECONDARY,
            "text-muted": TEXT_MUTED,
            "border-light": BORDER_LIGHT,
            "border-medium": BORDER_MEDIUM,
        },
    )
