"""Centralized color theme for the DeepSeek CLI terminal UI.

All widgets should import from this module instead of hardcoding colors.
Usage:
    from app.theme import ACCENT, BG_WIDGET, TEXT_PRIMARY
"""

# ── Palette ──────────────────────────────────────────────

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
