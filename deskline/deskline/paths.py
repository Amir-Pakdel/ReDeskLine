"""Locations Deskline owns under the user profile."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Deskline"
CONFIG_PATH = DATA / "config.json"
SESSION_PATH = DATA / "session.json"
WALLPAPER_STATUS = DATA / "wallpaper-status.json"
LOG_PATH = DATA / "deskline.log"


def ensure_data_dir() -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    return DATA
