"""Taskbar scroll-volume and keyboard/mouse clicks. Hooks stop when the switches are off."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QSoundEffect, QAudioOutput

from deskline import winutil
from deskline.sounds import sound_path

user32 = ctypes.windll.user32
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_MOUSEWHEEL = 0x020A
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
LLKHF_INJECTED = 0x10
VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
KEYEVENTF_KEYUP = 0x0002

user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_uint, ctypes.c_size_t]


class _PointData(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("data", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("extra", ctypes.c_size_t),
    ]


class InputHooks(QObject):
    def __init__(self):
        super().__init__()
        self.scroll = False
        self.scroll_steps = 1
        self.keys = False
        self.mouse = False
        self.key_volume = 0.7
        self.mouse_volume = 0.5
        self.scape = False
        self.scape_volume = 0.4
        self.paused = False
        self._mouse_hook = None
        self._key_hook = None
        self._mouse_cb = None
        self._key_cb = None
        self.key_sound = QSoundEffect(self)
        self.mouse_sound = QSoundEffect(self)
        self.key_sound.setSource(QUrl.fromLocalFile(sound_path("key")))
        self.mouse_sound.setSource(QUrl.fromLocalFile(sound_path("mouse")))
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.player.setSource(QUrl.fromLocalFile(sound_path("scape")))
        self.pack_dir = ""
        self._pack_sounds: dict[str, QSoundEffect] = {}

    def apply(self, taskbar: dict, audio: dict, paused: bool) -> None:
        self.paused = paused
        self.scroll = bool(taskbar.get("scroll_volume")) and not paused
        percent = int(taskbar.get("scroll_percent") or 2)
        self.scroll_steps = {1: 1, 2: 1, 5: 3, 10: 5}.get(percent, 1)
        self.keys = bool(audio.get("keyboard")) and not paused
        self.mouse = bool(audio.get("mouse")) and not paused
        self.key_volume = max(0.0, min(1.0, int(audio.get("key_volume") or 70) / 100))
        self.mouse_volume = max(0.0, min(1.0, int(audio.get("mouse_volume") or 50) / 100))
        self.key_sound.setVolume(self.key_volume)
        self.mouse_sound.setVolume(self.mouse_volume)
        self._bind(self.key_sound, str(audio.get("key_file") or ""), sound_path("key"))
        self._bind(self.mouse_sound, str(audio.get("mouse_file") or ""), sound_path("mouse"))
        self.pack_dir = str(audio.get("sound_pack") or "")
        want_scape = bool(audio.get("scape")) and not paused
        self.audio.setVolume(max(0.0, min(1.0, int(audio.get("scape_volume") or 40) / 100)))
        if want_scape and self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.player.play()
        elif not want_scape and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        self._ensure(self.scroll or self.mouse, self.keys)

    def _bind(self, effect: QSoundEffect, configured: str, fallback: str) -> None:
        path = configured if configured and os.path.isfile(configured) else fallback
        if getattr(effect, "_deskline_path", None) == path:
            return
        effect.setSource(QUrl.fromLocalFile(path))
        effect._deskline_path = path

    def shutdown(self) -> None:
        self.player.stop()
        self._ensure(False, False)

    def _ensure(self, mouse: bool, keys: bool) -> None:
        module = ctypes.windll.kernel32.GetModuleHandleW(None)
        if mouse and not self._mouse_hook:
            self._mouse_cb = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)(self._mouse)
            self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_cb, module, 0)
        elif not mouse and self._mouse_hook:
            user32.UnhookWindowsHookEx(self._mouse_hook)
            self._mouse_hook = None
        if keys and not self._key_hook:
            self._key_cb = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)(self._key)
            self._key_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._key_cb, module, 0)
        elif not keys and self._key_hook:
            user32.UnhookWindowsHookEx(self._key_hook)
            self._key_hook = None

    def _mouse(self, code, wparam, lparam):
        if code >= 0 and not self.paused:
            info = ctypes.cast(lparam, ctypes.POINTER(_PointData)).contents
            if wparam == WM_MOUSEWHEEL and self.scroll and winutil.point_on_taskbar(info.x, info.y):
                delta = ctypes.c_short(info.data >> 16).value
                self._volume(delta > 0)
                return 1
            if self.mouse and wparam in {WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP}:
                names = {
                    WM_LBUTTONDOWN: "left", WM_LBUTTONUP: "left",
                    WM_RBUTTONDOWN: "right", WM_RBUTTONUP: "right",
                    WM_MBUTTONDOWN: "middle", WM_MBUTTONUP: "middle",
                }
                self._play_pack(names.get(int(wparam), ""), self.mouse_sound)
        return user32.CallNextHookEx(self._mouse_hook, code, wparam, lparam)

    def _key(self, code, wparam, lparam):
        if code >= 0 and self.keys and not self.paused and wparam in {WM_KEYDOWN, WM_KEYUP}:
            class _KeyData(ctypes.Structure):
                _fields_ = [
                    ("vk", wintypes.DWORD),
                    ("scan", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("extra", ctypes.c_size_t),
                ]
            info = ctypes.cast(lparam, ctypes.POINTER(_KeyData)).contents
            if not info.flags & LLKHF_INJECTED:
                self._play_pack(str(int(info.vk)), self.key_sound)
        return user32.CallNextHookEx(self._key_hook, code, wparam, lparam)

    def _play_pack(self, name: str, fallback: QSoundEffect) -> None:
        folder = self.pack_dir
        path = ""
        if folder and name:
            for candidate in (os.path.join(folder, f"{name}.wav"), os.path.join(folder, "default.wav")):
                if os.path.isfile(candidate):
                    path = candidate
                    break
        if not path:
            fallback.play()
            return
        effect = self._pack_sounds.get(path)
        if effect is None:
            effect = QSoundEffect(self)
            effect.setSource(QUrl.fromLocalFile(path))
            self._pack_sounds[path] = effect
        effect.setVolume(fallback.volume())
        effect.play()

    def _volume(self, up: bool) -> None:
        key = VK_VOLUME_UP if up else VK_VOLUME_DOWN
        for _ in range(self.scroll_steps):
            user32.keybd_event(key, 0, 0, 0)
            user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
