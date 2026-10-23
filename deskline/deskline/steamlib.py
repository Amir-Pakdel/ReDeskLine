"""Installed Steam games from the local library files. Nothing is downloaded."""

from __future__ import annotations

import os
import re
from pathlib import Path


def _steam_install() -> Path | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _kind = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return None
    path = Path(str(value))
    return path if path.is_dir() else None


def _library_roots() -> list[Path]:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam",
        Path.home() / "Steam",
    ]
    installed = _steam_install()
    if installed is not None:
        candidates.insert(0, installed)
    roots: list[Path] = []
    seen: set[str] = set()
    for root in candidates:
        folders = root / "steamapps" / "libraryfolders.vdf"
        if not folders.is_file():
            continue
        text = folders.read_text(encoding="utf-8", errors="replace")
        paths = re.findall(r'"path"\s+"([^"]+)"', text)
        if not paths:
            paths = [str(root)]
        for raw in paths:
            folder = Path(raw.replace("\\\\", "\\"))
            key = str(folder).lower()
            if key not in seen and (folder / "steamapps").is_dir():
                seen.add(key)
                roots.append(folder)
    return roots


def installed_games() -> list[dict]:
    games: list[dict] = []
    seen: set[str] = set()
    for root in _library_roots():
        for manifest in (root / "steamapps").glob("appmanifest_*.acf"):
            text = manifest.read_text(encoding="utf-8", errors="replace")
            appid = _field(text, "appid")
            name = _field(text, "name")
            state = _field(text, "StateFlags")
            if not appid or not name or appid in seen:
                continue
            if state and state not in {"4", "6"}:
                continue
            seen.add(appid)
            games.append({"appid": appid, "name": name})
    games.sort(key=lambda item: item["name"].lower())
    return games


def _field(text: str, name: str) -> str:
    match = re.search(rf'"{name}"\s+"([^"]*)"', text)
    return match.group(1) if match else ""
