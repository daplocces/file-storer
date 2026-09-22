import os
import ctypes
import tkinter.font as tkfont

from constants import FONT_FAMILY_PRIMARY, FONT_FALLBACK

FR_PRIVATE = 0x10

def load_app_font(assets_dir):
    """Loads Montserrat-Bold.ttf as a private font (Windows only) and
    returns the font family name to actually use (falls back safely)."""
    ttf_path = os.path.join(assets_dir, "Montserrat-Bold.ttf")
    if os.name == "nt" and os.path.exists(ttf_path):
        try:
            ctypes.windll.gdi32.AddFontResourceExW(ttf_path, FR_PRIVATE, 0)
        except Exception:
            pass

    available = set(tkfont.families())
    if FONT_FAMILY_PRIMARY in available:
        return FONT_FAMILY_PRIMARY
    return FONT_FALLBACK