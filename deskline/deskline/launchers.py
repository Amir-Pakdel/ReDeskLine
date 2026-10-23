"""Start-menu shortcuts Deskline can show and open. Shortcuts are not copied."""

from __future__ import annotations

import os
from pathlib import Path

_cache: tuple[float, list[dict]] = (0.0, [])


def start_menu_apps() -> list[dict]:
    global _cache
    import time
    cached_at, cached = _cache
    if cached and time.monotonic() - cached_at < 30:
        return list(cached)
    roots = []
    program_data = os.environ.get("ProgramData", "")
    appdata = os.environ.get("APPDATA", "")
    if program_data:
        roots.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    apps: list[dict] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.lnk"):
            name = path.stem.strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            apps.append({"name": name, "path": str(path)})
    apps.sort(key=lambda item: item["name"].lower())
    _cache = (time.monotonic(), apps)
    return list(apps)


def open_path(path: str) -> None:
    os.startfile(path)
