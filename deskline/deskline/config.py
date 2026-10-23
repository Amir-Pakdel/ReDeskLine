"""JSON settings and the short-lived session file shared with the wallpaper process."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from deskline.paths import CONFIG_PATH, LOG_PATH, SESSION_PATH, ensure_data_dir

DEFAULTS: dict[str, Any] = {
    "wallpaper": {
        "enabled": False,
        "path": "",
        "blur": 0,
        "brightness": 0,
        "muted": True,
        "hide_icons": False,
        "previous_static": "",
        "active_id": "",
        "overlay": "none",
        "overlay_color": "#ffffff",
        "overlay_amount": 50,
        "slideshow": False,
        "slideshow_minutes": 10,
        "source": "media",
        "url": "",
        "shader": "plasma",
        "pause_battery": False,
        "pause_apps": "",
        "idle_screensaver": False,
        "idle_minutes": 5,
        "all_monitors": False,
    },
    "taskbar": {
        "enabled": False,
        "clear": True,
        "scroll_volume": False,
        "scroll_percent": 2,
        "hide_maximized": False,
        "blur": 0,
        "brightness": 0,
        "height": 100,
        "side_gap": 0,
        "corners": 0,
        "show_bar": False,
        "bar_width": 40,
        "bar_height": 100,
        "bar_radius": 0,
        "bar_opacity": 55,
        "bar_mode": "cover",
        "bar_color": "black",
        "design": "wave",
        "gif": "",
        "accent": "clear",
        "accent_color": "#000000",
        "accent_opacity": 40,
        "dynamic_maximized": "same",
        "shape_margin": 0,
        "shape_radius": 0,
        "dock": False,
        "dock_width": 60,
    },
    "cursor": {
        "enabled": False,
        "color": "#ff3b5c",
        "mode": "single",
        "move": "classic",
        "left_click": "shockwave",
        "right_click": "same",
        "amount": 50,
        "size": 50,
        "length": 50,
        "glow": 55,
        "spread": 50,
        "pointer": "system",
        "pointer_gif": "",
    },
    "widgets": {
        "clock": False,
        "monitor": False,
        "music": False,
        "games": False,
        "disk": False,
        "net": False,
        "notes": False,
        "launch": False,
        "locked": False,
        "clock_x": 80,
        "clock_y": 80,
        "monitor_x": 80,
        "monitor_y": 220,
        "music_x": 80,
        "music_y": 340,
        "games_x": 420,
        "games_y": 80,
        "disk_x": 80,
        "disk_y": 460,
        "net_x": 320,
        "net_y": 460,
        "notes_x": 80,
        "notes_y": 560,
        "launch_x": 560,
        "launch_y": 80,
        "notes_text": "",
        "launch_query": "",
        "hour24": True,
        "seconds": True,
        "weekday": True,
        "uppercase": True,
        "show_date": True,
    },
    "windows": {
        "accent": "#ff3b5c",
        "accent_from_wallpaper": False,
        "schedule": False,
        "light_from": "07:00",
        "dark_from": "19:00",
        "saved_apps_light": None,
        "saved_system_light": None,
        "classic_menu": False,
    },
    "retro": {
        "left_taskbar": False,
        "compact_taskbar": False,
        "glass": False,
        "saved_align": None,
        "saved_size": None,
        "saved_transparency": None,
    },
    "game": {
        "enabled": False,
        "max_performance": True,
        "priority": False,
        "pause_effects": True,
    },
    "audio": {
        "keyboard": False,
        "mouse": False,
        "key_volume": 70,
        "mouse_volume": 50,
        "scape": False,
        "scape_volume": 40,
        "rain": 0,
        "wind": 0,
        "birds": 0,
        "city": 0,
        "thunder": 0,
        "plug_chime": False,
        "key_file": "",
        "mouse_file": "",
        "eq": False,
        "eq_bass": 0,
        "eq_mid": 0,
        "eq_treble": 0,
        "eq_bands": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "sound_pack": "",
    },
    "tools": {
        "awake": False,
        "awake_minutes": 60,
        "awake_screen": True,
        "hotkey": True,
    },
    "checks": [],
}


def _merge(base: dict, incoming: dict) -> dict:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read(path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(path, data: dict) -> None:
    ensure_data_dir()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


class Config:
    def __init__(self) -> None:
        self.data = _merge(DEFAULTS, _read(CONFIG_PATH))
        self._mtime = 0.0
        self.save()

    def reload_if_changed(self) -> bool:
        """Pick up edits from Revision Tool without opening a second window."""
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            return False
        if mtime <= self._mtime:
            return False
        self.data = _merge(DEFAULTS, _read(CONFIG_PATH))
        self._mtime = mtime
        return True

    def section(self, name: str) -> dict:
        value = self.data.get(name, {})
        return value if isinstance(value, dict) else {}

    def update_section(self, name: str, **values: Any) -> None:
        current = dict(self.section(name))
        current.update(values)
        self.data[name] = current
        self.save()

    def save(self) -> None:
        _write(CONFIG_PATH, self.data)
        try:
            self._mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            self._mtime = 0.0


class Session:
    def __init__(self) -> None:
        self.data = {
            "stop_wallpaper": False,
            "pause_effects": False,
            "boosting": False,
            "saved_scheme": None,
            "priority_pid": None,
        }
        self.data.update(_read(SESSION_PATH))
        self.save()

    def set(self, **values: Any) -> None:
        self.data.update(values)
        self.save()

    def save(self) -> None:
        _write(SESSION_PATH, self.data)


def read_session() -> dict:
    return _read(SESSION_PATH)


def log(message: str) -> None:
    ensure_data_dir()
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        return
