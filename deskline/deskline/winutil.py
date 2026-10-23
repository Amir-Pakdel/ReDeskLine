"""Small Win32 helpers. Handles stay pointer-sized so 64-bit HWNDs are not truncated."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

user32.FindWindowW.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowExW.restype = ctypes.c_void_p
user32.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.SetParent.restype = ctypes.c_void_p
user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetParent.restype = ctypes.c_void_p
user32.GetParent.argtypes = [ctypes.c_void_p]
user32.GetWindow.restype = ctypes.c_void_p
user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowPos.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
user32.IsWindow.argtypes = [ctypes.c_void_p]
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.GetCursorPos.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.ScreenToClient.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.SetLayeredWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_byte, ctypes.c_uint]
user32.SendMessageTimeoutW.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p,
    ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
]
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.MonitorFromWindow.restype = ctypes.c_void_p
user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
kernel32.SetThreadExecutionState.restype = ctypes.c_uint
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x00000002
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
HWND_TOPMOST = ctypes.c_void_p(-1)
HWND_NOTOPMOST = ctypes.c_void_p(-2)
GW_HWNDNEXT = 2
GW_HWNDPREV = 3
WM_HOTKEY = 0x0312
WM_COMMAND = 0x0111
WM_ERASEBKGND = 0x0014
TOGGLE_DESKTOP_ICONS = 0x7402
SPAWN_WORKER = 0x052C
MOD_CONTROL = 0x0002
MOD_WIN = 0x0008
VK_T = 0x54
HOTKEY_ID = 1

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

PROCESS_SET_INFORMATION = 0x0200
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
NORMAL_PRIORITY_CLASS = 0x00000020

ACCENT_DISABLED = 0
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
WCA_ACCENT_POLICY = 19

DESKTOP_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
}


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


class ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def enable_dpi_awareness() -> None:
    """Per-monitor v2, before any window exists. Failure means Windows already chose a mode."""
    try:
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_int
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        return


def idle_seconds() -> float:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo.argtypes = [ctypes.c_void_p]
    user32.GetLastInputInfo.restype = ctypes.c_int
    kernel32.GetTickCount.restype = ctypes.c_uint
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    elapsed = int(kernel32.GetTickCount() - info.dwTime)
    if elapsed < 0:
        elapsed += 2**32
    return elapsed / 1000


def acquire_single_instance() -> bool:
    kernel32.CreateMutexW(None, False, "Local\\Deskline.SingleInstance")
    return kernel32.GetLastError() != 183


def _text(hwnd, getter, size=256) -> str:
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(size)
    getter(hwnd, buf, size)
    return buf.value


def window_title(hwnd) -> str:
    return _text(hwnd, user32.GetWindowTextW)


def window_class(hwnd) -> str:
    return _text(hwnd, user32.GetClassNameW)


def window_rect(hwnd) -> RECT | None:
    rect = RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect


def window_cloaked(hwnd: int) -> bool:
    """True when DWM is not drawing the window, including an auto-hidden taskbar."""
    if not hwnd:
        return False
    dwmapi = ctypes.windll.dwmapi
    dwmapi.DwmGetWindowAttribute.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
    ]
    dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    value = ctypes.c_int(0)
    result = dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(value), ctypes.sizeof(value))
    return result == 0 and value.value != 0


def find_window(class_name: str) -> int:
    return int(user32.FindWindowW(class_name, None) or 0)


def find_child(parent: int, class_name: str) -> int:
    return int(user32.FindWindowExW(parent or None, None, class_name, None) or 0)


def is_raised_desktop() -> bool:
    """Windows 11 24H2+ keeps the icons directly inside Progman."""
    progman = find_window("Progman")
    return bool(progman and find_child(progman, "SHELLDLL_DefView"))


def _spawn_worker(progman: int) -> None:
    user32.SendMessageTimeoutW(progman, SPAWN_WORKER, 0xD, 0x1, 0, 1000, None)


def _classic_workerw() -> int:
    found = {"hwnd": 0}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            worker = user32.FindWindowExW(None, hwnd, "WorkerW", None)
            if worker:
                found["hwnd"] = int(worker)
        return True

    user32.EnumWindows(callback, 0)
    return found["hwnd"]


def wallpaper_parent() -> int:
    progman = find_window("Progman")
    if not progman:
        return 0
    if is_raised_desktop():
        if not find_child(progman, "WorkerW"):
            _spawn_worker(progman)
        return progman
    worker = _classic_worker()
    if not worker:
        _spawn_worker(progman)
        worker = _classic_worker()
    return worker


def _as_child(hwnd: int, parent: int) -> None:
    rect = window_rect(hwnd)
    if rect is None:
        return
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not ex_style & WS_EX_LAYERED:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    user32.SetWindowLongW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD)
    user32.SetParent(hwnd, parent)
    pt = POINT(rect.left, rect.top)
    user32.ScreenToClient(parent, ctypes.byref(pt))
    user32.SetWindowPos(
        hwnd, None, pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top,
        SWP_NOZORDER | SWP_NOACTIVATE,
    )


def _order_under_icons(hwnd: int, progman: int) -> None:
    defview = find_child(progman, "SHELLDLL_DefView")
    if not defview:
        return
    if int(user32.GetWindow(hwnd, GW_HWNDPREV) or 0) != defview:
        user32.SetWindowPos(hwnd, defview, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    worker = find_child(progman, "WorkerW")
    if worker and user32.GetWindow(worker, GW_HWNDNEXT):
        user32.SetWindowPos(worker, ctypes.c_void_p(1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _reposition(hwnd: int, parent: int) -> None:
    rect = window_rect(hwnd)
    if rect is None:
        return
    pt = POINT(rect.left, rect.top)
    user32.ScreenToClient(parent, ctypes.byref(pt))
    user32.SetWindowPos(
        hwnd, None, pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top,
        SWP_NOZORDER | SWP_NOACTIVATE,
    )


def attach_wallpaper(hwnd: int) -> bool:
    parent = wallpaper_parent()
    if not parent or not hwnd:
        return False
    if is_raised_desktop():
        _as_child(hwnd, parent)
        _order_under_icons(hwnd, parent)
    else:
        user32.SetParent(hwnd, parent)
        _reposition(hwnd, parent)
    return int(user32.GetParent(hwnd) or 0) == parent


def ensure_wallpaper_attached(hwnd: int) -> bool:
    parent = wallpaper_parent()
    if not parent or not hwnd:
        return False
    if int(user32.GetParent(hwnd) or 0) != parent:
        return attach_wallpaper(hwnd)
    if is_raised_desktop():
        _order_under_icons(hwnd, parent)
    return True


def detach_wallpaper(hwnd: int) -> None:
    if not hwnd or not user32.IsWindow(hwnd):
        return
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    user32.SetWindowLongW(hwnd, GWL_STYLE, (style & ~WS_CHILD) | WS_POPUP)
    user32.SetParent(hwnd, None)
    user32.ShowWindow(hwnd, 0)


def make_click_through(hwnd: int, topmost: bool = True) -> None:
    if not hwnd:
        return
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
    if topmost:
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
    else:
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags | SWP_NOZORDER)


def place_behind(hwnd: int, anchor: int) -> None:
    if hwnd and anchor:
        user32.SetWindowPos(hwnd, anchor, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def set_taskbar_transparent(clear: bool) -> bool:
    hwnd = find_window("Shell_TrayWnd")
    if not hwnd:
        return False
    try:
        user32.SetWindowCompositionAttribute.argtypes = [ctypes.c_void_p, ctypes.POINTER(WINCOMPATTRDATA)]
        user32.SetWindowCompositionAttribute.restype = ctypes.c_int
    except Exception:
        return False
    policy = ACCENTPOLICY()
    policy.AccentState = ACCENT_ENABLE_TRANSPARENTGRADIENT if clear else ACCENT_DISABLED
    policy.AccentFlags = 2 if clear else 0
    policy.GradientColor = 0x01000000 if clear else 0
    data = WINCOMPATTRDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.Data = ctypes.addressof(policy)
    data.SizeOfData = ctypes.sizeof(policy)
    return bool(user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data)))


def toggle_desktop_icons() -> bool:
    progman = find_window("Progman")
    if not progman:
        return False
    target = find_child(progman, "SHELLDLL_DefView")
    if not target:
        found = {"hwnd": 0}

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def callback(hwnd, _lparam):
            view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
            if view:
                found["hwnd"] = int(view)
            return True

        user32.EnumWindows(callback, 0)
        target = found["hwnd"]
    if not target:
        return False
    user32.SendMessageW(target, WM_COMMAND, TOGGLE_DESKTOP_ICONS, 0)
    return True


def _monitor_from(hwnd: int) -> RECT | None:
    monitor = user32.MonitorFromWindow(hwnd, 2)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    return info.rcMonitor


def taskbar_appbar_state() -> int:
    data = _appbar_data()
    return int(shell32.SHAppBarMessage(4, ctypes.byref(data)))


def set_taskbar_appbar_state(state: int) -> None:
    data = _appbar_data()
    data.lParam = int(state)
    shell32.SHAppBarMessage(10, ctypes.byref(data))


def _appbar_data():
    class APPBARDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("hWnd", ctypes.c_void_p),
            ("uCallbackMessage", ctypes.c_uint),
            ("uEdge", ctypes.c_uint),
            ("rc", RECT),
            ("lParam", ctypes.c_size_t),
        ]

    shell32.SHAppBarMessage.argtypes = [ctypes.c_uint, ctypes.POINTER(APPBARDATA)]
    shell32.SHAppBarMessage.restype = ctypes.c_size_t
    data = APPBARDATA()
    data.cbSize = ctypes.sizeof(APPBARDATA)
    data.hWnd = find_window("Shell_TrayWnd") or None
    return data


def point_on_taskbar(x: int, y: int) -> bool:
    rect = window_rect(find_window("Shell_TrayWnd"))
    if rect is None:
        return False
    if not (rect.left <= x <= rect.right and rect.top <= y <= rect.bottom):
        return False
    clock = _clock_rect(rect)
    if clock and clock.left <= x <= clock.right and clock.top <= y <= clock.bottom:
        return False
    return True


def _clock_rect(taskbar: RECT) -> RECT | None:
    found = {"hwnd": 0}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        name = window_class(int(hwnd))
        if "Clock" in name or name in {"TrayClockW32", "ClockButton"}:
            found["hwnd"] = int(hwnd)
            return False
        return True

    tray = find_window("Shell_TrayWnd")
    if tray:
        user32.EnumChildWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        user32.EnumChildWindows(tray, callback, 0)
    if found["hwnd"]:
        return window_rect(found["hwnd"])
    fallback = RECT()
    fallback.left = taskbar.right - 180
    fallback.top = taskbar.top
    fallback.right = taskbar.right
    fallback.bottom = taskbar.bottom
    return fallback


def foreground_maximized() -> bool:
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd or window_class(hwnd) in DESKTOP_CLASSES or window_title(hwnd).startswith("Deskline"):
        return False
    user32.IsZoomed.argtypes = [ctypes.c_void_p]
    user32.IsZoomed.restype = ctypes.c_int
    return bool(user32.IsZoomed(hwnd))


def foreground_fullscreen() -> tuple[int, str] | None:
    """Return pid and window title when the foreground window covers its monitor."""
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return None
    cls = window_class(hwnd)
    if cls in DESKTOP_CLASSES:
        return None
    title = window_title(hwnd)
    if title.startswith("Deskline"):
        return None
    rect = window_rect(hwnd)
    monitor = _monitor_from(hwnd)
    if rect is None or monitor is None:
        return None
    covers = (
        rect.left <= monitor.left + 2
        and rect.top <= monitor.top + 2
        and rect.right >= monitor.right - 2
        and rect.bottom >= monitor.bottom - 2
    )
    if not covers:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    return int(pid.value), title


def set_priority(pid: int, above_normal: bool) -> bool:
    access = PROCESS_SET_INFORMATION
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return False
    try:
        level = ABOVE_NORMAL_PRIORITY_CLASS if above_normal else NORMAL_PRIORITY_CLASS
        return bool(kernel32.SetPriorityClass(handle, level))
    finally:
        kernel32.CloseHandle(handle)


def set_awake(system: bool, display: bool) -> None:
    flags = ES_CONTINUOUS
    if system:
        flags |= ES_SYSTEM_REQUIRED
    if display:
        flags |= ES_DISPLAY_REQUIRED
    kernel32.SetThreadExecutionState(flags)


def clear_awake() -> None:
    kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def register_topmost_hotkey(hwnd: int) -> bool:
    return bool(user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_WIN, VK_T))


def unregister_topmost_hotkey(hwnd: int) -> None:
    if hwnd:
        user32.UnregisterHotKey(hwnd, HOTKEY_ID)


def toggle_topmost(hwnd: int) -> bool:
    if not hwnd:
        return False
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    top = bool(ex_style & WS_EX_TOPMOST)
    insert = HWND_NOTOPMOST if top else HWND_TOPMOST
    return bool(user32.SetWindowPos(
        hwnd, insert, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    ))


def foreground_hwnd() -> int:
    return int(user32.GetForegroundWindow() or 0)


def restart_explorer() -> None:
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=creation, check=False)
    subprocess.Popen(["explorer.exe"], creationflags=creation)


def open_settings(page: str) -> None:
    os_start(f"ms-settings:{page}")


def os_start(target: str) -> None:
    if sys.platform == "win32":
        os_startfile(target)
    else:
        subprocess.Popen([target])


def os_startfile(target: str) -> None:
    import os
    os.startfile(target)  # noqa: S606 — user-requested Windows settings page or folder


def current_wallpaper_path() -> str:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            value, _ = winreg.QueryValueEx(key, "WallPaper")
            return str(value)
    except OSError:
        return ""


def set_static_wallpaper(path: str) -> bool:
    if not path or not Path(path).is_file():
        return False
    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    user32.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
    return bool(user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE))


def broadcast_setting(name: str) -> None:
    buf = ctypes.create_unicode_buffer(name)
    user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, ctypes.cast(buf, ctypes.c_void_p), 0x0002, 200, None)


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


def erase_background_handled(message_ptr: int) -> bool:
    """True when this native message is WM_ERASEBKGND and should not flash black."""
    try:
        msg = _MSG.from_address(int(message_ptr))
    except (ValueError, TypeError):
        return False
    return msg.message == WM_ERASEBKGND
