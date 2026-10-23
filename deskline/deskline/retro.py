"""Reversible taskbar alignment, compact size, and Windows transparency."""

from __future__ import annotations

from deskline.tweaks import _dword, _set_dword
from deskline.winutil import broadcast_setting

ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def read_layout() -> tuple[int | None, int | None, int | None]:
    return (
        _dword(ADVANCED, "TaskbarAl"),
        _dword(ADVANCED, "TaskbarSi"),
        _dword(PERSONALIZE, "EnableTransparency"),
    )


def set_left_taskbar(enabled: bool, previous: int | None) -> int | None:
    if enabled:
        saved = previous if previous is not None else (_dword(ADVANCED, "TaskbarAl") if _dword(ADVANCED, "TaskbarAl") is not None else 1)
        _set_dword(ADVANCED, "TaskbarAl", 0)
        return int(saved)
    if previous is not None:
        _set_dword(ADVANCED, "TaskbarAl", int(previous))
    return None


def set_compact_taskbar(enabled: bool, previous: int | None) -> int | None:
    if enabled:
        saved = previous if previous is not None else (_dword(ADVANCED, "TaskbarSi") if _dword(ADVANCED, "TaskbarSi") is not None else 1)
        _set_dword(ADVANCED, "TaskbarSi", 0)
        return int(saved)
    if previous is not None:
        _set_dword(ADVANCED, "TaskbarSi", int(previous))
    return None


def set_glass(enabled: bool, previous: int | None) -> int | None:
    if enabled:
        saved = previous if previous is not None else (_dword(PERSONALIZE, "EnableTransparency") if _dword(PERSONALIZE, "EnableTransparency") is not None else 1)
        _set_dword(PERSONALIZE, "EnableTransparency", 1)
        broadcast_setting("ImmersiveColorSet")
        return int(saved)
    if previous is not None:
        _set_dword(PERSONALIZE, "EnableTransparency", int(previous))
        broadcast_setting("ImmersiveColorSet")
    return None
