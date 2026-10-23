"""Reversible Windows appearance settings. Each change records the previous value."""

from __future__ import annotations

import winreg
from datetime import datetime

from deskline.winutil import broadcast_setting

PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
DWM = r"Software\Microsoft\Windows\DWM"
CLASSIC_MENU = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"


def _dword(path: str, name: str) -> int | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    if kind != winreg.REG_DWORD:
        return None
    return int(value)


def _set_dword(path: str, name: str, value: int) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))


def read_theme_light() -> tuple[int | None, int | None]:
    return _dword(PERSONALIZE, "AppsUseLightTheme"), _dword(PERSONALIZE, "SystemUsesLightTheme")


def set_theme_light(light: bool) -> None:
    value = 1 if light else 0
    _set_dword(PERSONALIZE, "AppsUseLightTheme", value)
    _set_dword(PERSONALIZE, "SystemUsesLightTheme", value)
    broadcast_setting("ImmersiveColorSet")


def restore_theme(apps: int | None, system: int | None) -> None:
    if apps is not None:
        _set_dword(PERSONALIZE, "AppsUseLightTheme", apps)
    if system is not None:
        _set_dword(PERSONALIZE, "SystemUsesLightTheme", system)
    broadcast_setting("ImmersiveColorSet")


def _hex_to_abgr(color: str) -> int:
    text = color.removeprefix("#")
    if len(text) != 6:
        text = "FF3B5C"
    red = int(text[0:2], 16)
    green = int(text[2:4], 16)
    blue = int(text[4:6], 16)
    return (0xFF << 24) | (blue << 16) | (green << 8) | red


def set_accent(color: str) -> None:
    abgr = _hex_to_abgr(color)
    _set_dword(DWM, "AccentColor", abgr)
    _set_dword(DWM, "ColorPrevalence", 1)
    _set_dword(PERSONALIZE, "ColorPrevalence", 1)
    broadcast_setting("ImmersiveColorSet")


def classic_menu_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLASSIC_MENU):
            return True
    except OSError:
        return False


def set_classic_menu(enabled: bool) -> None:
    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLASSIC_MENU) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "")
        return
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLASSIC_MENU)
    except OSError:
        return
    parent = CLASSIC_MENU.rsplit("\\", 1)[0]
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, parent)
    except OSError:
        return


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour, minute = value.split(":", 1)
        return max(0, min(23, int(hour))), max(0, min(59, int(minute)))
    except (ValueError, AttributeError):
        return 7, 0


def light_wanted(now: datetime, light_from: str, dark_from: str) -> bool:
    hour, minute = now.hour, now.minute
    start = parse_hhmm(light_from)
    end = parse_hhmm(dark_from)
    current = (hour, minute)
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end
