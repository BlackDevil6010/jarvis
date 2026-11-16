"""Configuration constants, color definitions, and default paths for JARVIS."""

import os
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()
except ImportError:
    pass

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jarvis.db"

ASSETS_DIR = BASE_DIR / "assets"
BRANDING_DIR = ASSETS_DIR / "branding"
LOGO_PATH = BRANDING_DIR / "jarvis_logo.png"
ICO_PATH = BRANDING_DIR / "jarvis_logo.ico"

# Application Metadata
APP_NAME = "O.M.E.N."
APP_SUBTITLE = "Tactical Desktop Assistant System"
APP_VERSION = "1.0.0 (Phase 1)"

# Palette - Futuristic Dark & Holographic Glassmorphism (Navy, Black, Cyan, Purple Accents)
COLORS = {
    "bg_root": "#050811",           # Deep space black
    "bg_panel": "#0b1220",          # Dark navy panel
    "bg_panel_elevated": "#101b30", # Slightly elevated navy panel
    "bg_input": "#070c18",          # Input box background
    "border_subtle": "#172b4d",     # Low-contrast cyan-navy border
    "border_highlight": "#00d2ff",  # Glowing cyan border
    "border_active": "#00f0ff",     # Vibrant cyan active border
    "text_primary": "#e6f1ff",      # Ice white text
    "text_secondary": "#7b9ec7",    # Slate blue secondary text
    "text_muted": "#415a77",        # Darker slate text
    "cyan_glow": "#00f0ff",         # Primary neon cyan
    "blue_accent": "#007acc",       # Primary blue accent
    "blue_hover": "#0098ff",        # Brighter hover blue
    "magenta_glow": "#bf00ff",      # Vibrant holographic magenta
    "purple_accent": "#8a2be2",     # Royal neon violet
    "glass_panel": "rgba(12, 20, 42, 0.72)",
    "glass_panel_elevated": "rgba(18, 30, 60, 0.82)",
    "glass_border_cyan": "rgba(0, 240, 255, 0.45)",
    "glass_border_purple": "rgba(191, 0, 255, 0.45)",
    "dock_bg": "rgba(10, 16, 36, 0.85)",
    "status_online": "#00f0ff",     # System ready / online
    "status_busy": "#ffb703",       # System processing / busy
    "status_error": "#ff3860",      # System error / alert
    "status_success": "#00e676",    # Success green-cyan
}
