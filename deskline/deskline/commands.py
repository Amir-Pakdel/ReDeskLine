"""One-shot actions Revision Tool runs inside the same Deskline engine folder."""

from __future__ import annotations

import json
import sys

from deskline.config import Config
from deskline import services, wallpaper_prep, winutil


def _emit(payload: object) -> None:
    json.dump(payload, sys.stdout, default=str)
    sys.stdout.write("\n")


def _import_wallpaper(path: str) -> None:
    entry = wallpaper_prep.prepare(path)
    kind, media = wallpaper_prep.media_for(entry, wallpaper_prep.screen_pixels()[1])
    Config().update_section(
        "wallpaper",
        active_id=entry.get("id"),
        path=media,
        enabled=True,
        source="media",
    )
    _emit({"ok": True, "kind": kind, "entry": entry})


def _select_wallpaper(entry_id: str) -> None:
    for entry in wallpaper_prep.list_library():
        if str(entry.get("id")) == entry_id:
            _kind, media = wallpaper_prep.media_for(entry, wallpaper_prep.screen_pixels()[1])
            Config().update_section(
                "wallpaper",
                active_id=entry_id,
                path=media,
                enabled=True,
                source="media",
            )
            _emit({"ok": True, "path": media})
            return
    _emit({"ok": False, "error": "That wallpaper is not in the library."})


def _remove_wallpaper() -> None:
    config = Config()
    active = str(config.section("wallpaper").get("active_id") or "")
    if active:
        wallpaper_prep.delete_entry(active)
    config.update_section("wallpaper", active_id="", path="", enabled=False)
    _emit({"ok": True})


def _cleanup_delete(category_id: str) -> None:
    for category in services.scan_cleanup():
        if category.get("id") == category_id:
            removed, failed = services.delete_category(category)
            _emit({"ok": True, "removed": removed, "failed": failed})
            return
    _emit({"ok": False, "error": "That cleanup category was not found."})


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _emit({"ok": False, "error": "Missing command."})
        return 2
    command = argv[1]
    try:
        if command == "import-wallpaper" and len(argv) >= 3:
            _import_wallpaper(argv[2])
        elif command == "select-wallpaper" and len(argv) >= 3:
            _select_wallpaper(argv[2])
        elif command == "remove-wallpaper":
            _remove_wallpaper()
        elif command == "list-wallpapers":
            _emit(wallpaper_prep.list_library())
        elif command == "pc-check":
            facts = services.machine_facts()
            facts.update(services.hardware_names())
            facts["benchmark"] = services.run_benchmark()
            _emit(facts)
        elif command == "network":
            _emit(services.network_report())
        elif command == "drivers":
            _emit(services.driver_report())
        elif command == "cleanup-scan":
            _emit(services.scan_cleanup())
        elif command == "cleanup-delete" and len(argv) >= 3:
            _cleanup_delete(argv[2])
        elif command == "add-power-plan":
            _emit({"ok": services.duplicate_high_performance()})
        elif command == "restart-explorer":
            winutil.restart_explorer()
            _emit({"ok": True})
        else:
            _emit({"ok": False, "error": f"Unknown command: {command}"})
            return 2
    except Exception as exc:
        _emit({"ok": False, "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
