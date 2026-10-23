"""Applies the saved settings: overlays, wallpaper process, power plan, and timers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

from deskline import eqapo, retro, services, taskbar_fx, tweaks, wallpaper_prep, winutil
from deskline.ambient import AmbientMixer
from deskline.config import Config, Session
from deskline.hooks import InputHooks
from deskline.overlays import ClockOverlay, CursorOverlay, GamesOverlay, MonitorOverlay, MusicOverlay, TaskbarOverlay
from deskline.widgets_extra import DiskOverlay, LaunchOverlay, NetOverlay, NotesOverlay
from deskline.pointer import PointerDriver
from deskline.paths import LOG_PATH, ROOT, WALLPAPER_STATUS, ensure_data_dir

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
SKIP_PROCESSES = {
    "explorer.exe",
    "searchhost.exe",
    "startmenuexperiencehost.exe",
    "shellexperiencehost.exe",
    "applicationframehost.exe",
    "python.exe",
    "pythonw.exe",
    "systemsettings.exe",
    "dwm.exe",
}


class Runtime(QObject):
    changed = Signal()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.session = Session()
        saved = self.session.data.get("saved_scheme")
        if self.session.data.get("boosting") and saved:
            services.set_scheme(str(saved))
        self.session.set(stop_wallpaper=False, pause_effects=False, boosting=False, saved_scheme=None, priority_pid=None)
        self.cursor = CursorOverlay()
        self.clock = ClockOverlay()
        self.monitor = MonitorOverlay()
        self.music = MusicOverlay()
        self.games = GamesOverlay()
        self.disk = DiskOverlay()
        self.net = NetOverlay()
        self.notes = NotesOverlay()
        self.launch = LaunchOverlay()
        self.taskbar = TaskbarOverlay()
        self.pointer = PointerDriver()
        self.mixer = AmbientMixer()
        self.clock.moved = lambda x, y: self.config.update_section("widgets", clock_x=x, clock_y=y)
        self.monitor.moved = lambda x, y: self.config.update_section("widgets", monitor_x=x, monitor_y=y)
        self.music.moved = lambda x, y: self.config.update_section("widgets", music_x=x, music_y=y)
        self.games.moved = lambda x, y: self.config.update_section("widgets", games_x=x, games_y=y)
        self.disk.moved = lambda x, y: self.config.update_section("widgets", disk_x=x, disk_y=y)
        self.net.moved = lambda x, y: self.config.update_section("widgets", net_x=x, net_y=y)
        self.notes.moved = lambda x, y: self.config.update_section("widgets", notes_x=x, notes_y=y)
        self.notes.on_text = lambda text: self.config.update_section("widgets", notes_text=text)
        self.launch.moved = lambda x, y: self.config.update_section("widgets", launch_x=x, launch_y=y)
        self._eq_key = None
        self._eq_written = False
        self._eq_status = "Equalizer APO is used only while this is on."
        self._wallpaper: subprocess.Popen | None = None
        self._wallpaper_mode: str | None = None
        self._pending_mode: str | None = None
        self._generation = 0
        self._fails = 0
        self._log_handle = None
        self._game_status = "Game Boost is off."
        self._priority_pid: int | None = None
        self._saved_scheme: str | None = None
        self._boosting = False
        self._awake_deadline: float | None = None
        self._hwnd = 0
        self._hotkey = False
        self._ticks = 0
        self.hooks = InputHooks()
        self._saved_taskbar_state: int | None = None
        self._taskbar_hidden: bool | None = None
        self._setting_snapshot = self._setting_view()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self.apply()

    def attach_window(self, hwnd: int) -> None:
        self._hwnd = hwnd
        self._sync_hotkey()

    def apply(self) -> None:
        allowed = not self.session.data.get("pause_effects")
        cursor = self.config.section("cursor")
        widgets = self.config.section("widgets")
        taskbar = self.config.section("taskbar")
        self.cursor.apply(cursor, bool(cursor.get("enabled")) and allowed)
        self.clock.apply(widgets, bool(widgets.get("clock")) and allowed)
        self.monitor.apply(widgets, bool(widgets.get("monitor")) and allowed)
        self.music.apply(widgets, bool(widgets.get("music")) and allowed)
        self.games.apply(widgets, bool(widgets.get("games")) and allowed)
        self.disk.apply(widgets, bool(widgets.get("disk")) and allowed)
        self.net.apply(widgets, bool(widgets.get("net")) and allowed)
        self.notes.apply(widgets, bool(widgets.get("notes")) and allowed)
        self.launch.apply(widgets, bool(widgets.get("launch")) and allowed)
        self.taskbar.apply(taskbar, bool(taskbar.get("enabled")) and allowed)
        self._sync_eq()
        self._sync_wallpaper()
        self._sync_awake()
        self._sync_hotkey()
        self._sync_behavior(allowed)

    def eq_status(self) -> str:
        return self._eq_status

    def game_status(self) -> str:
        return self._game_status

    def wallpaper_status(self) -> str:
        mode = self._wanted_mode()
        if mode is None:
            return "Wallpaper is off."
        if mode == "image":
            return "Still image is set as the Windows wallpaper."
        try:
            data = json.loads(WALLPAPER_STATUS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if data.get("message"):
            return str(data["message"])
        if self._wallpaper and self._wallpaper.poll() is None:
            return "Starting the wallpaper…"
        return "Wallpaper is off."

    def toggle_topmost(self) -> None:
        hwnd = winutil.foreground_hwnd()
        if hwnd and hwnd != self._hwnd:
            winutil.toggle_topmost(hwnd)

    def _wanted_mode(self) -> str | None:
        section = self.config.section("wallpaper")
        if not section.get("enabled"):
            return None
        source = str(section.get("source") or "media")
        if source == "web":
            url = str(section.get("url") or "")
            return "web" if url.startswith(("http://", "https://")) else None
        if source == "shader":
            return "shader"
        kind, path, _name = wallpaper_prep.resolve(section)
        if not path or not os.path.isfile(path):
            return None
        if kind == "image":
            return "image"
        if wallpaper_prep.needs_paint(section):
            return "paint"
        return "video"

    def _sync_behavior(self, allowed: bool) -> None:
        audio = self.config.section("audio")
        cursor = self.config.section("cursor")
        self.hooks.apply(self.config.section("taskbar"), audio, not allowed)
        self.mixer.apply(audio, not allowed)
        self.pointer.apply(cursor, bool(cursor.get("enabled")) and allowed)
        section = self.config.section("taskbar")
        taskbar_fx.apply(section, bool(section.get("enabled")), winutil.foreground_maximized())
        if section.get("hide_maximized") and allowed:
            if self._saved_taskbar_state is None:
                self._saved_taskbar_state = winutil.taskbar_appbar_state()
            hide = winutil.foreground_maximized() or winutil.foreground_fullscreen() is not None
            if hide != self._taskbar_hidden:
                state = (int(self._saved_taskbar_state) | 0x1 | 0x2) if hide else int(self._saved_taskbar_state)
                winutil.set_taskbar_appbar_state(state)
                self._taskbar_hidden = hide
            return
        if self._saved_taskbar_state is not None:
            winutil.set_taskbar_appbar_state(int(self._saved_taskbar_state))
            self._saved_taskbar_state = None
            self._taskbar_hidden = None

    def _sync_wallpaper(self) -> None:
        mode = self._wanted_mode()
        if mode == "image":
            self._use_static_image()
            self._request_stop(None)
            return
        if mode is None:
            self._restore_static_image()
            self._request_stop(None)
            return
        alive = self._wallpaper is not None and self._wallpaper.poll() is None
        if alive and self._wallpaper_mode == mode:
            return
        self._request_stop(mode)

    def _use_static_image(self) -> None:
        section = self.config.section("wallpaper")
        if not section.get("previous_static"):
            self.config.update_section("wallpaper", previous_static=winutil.current_wallpaper_path())
        _kind, path, _name = wallpaper_prep.resolve(section)
        winutil.set_static_wallpaper(path)

    def _restore_static_image(self) -> None:
        previous = str(self.config.section("wallpaper").get("previous_static") or "")
        if previous and os.path.isfile(previous):
            winutil.set_static_wallpaper(previous)
            self.config.update_section("wallpaper", previous_static="")

    def _request_stop(self, next_mode: str | None) -> None:
        self._generation += 1
        generation = self._generation
        self._pending_mode = next_mode
        proc = self._wallpaper
        if proc is None or proc.poll() is not None:
            self._wallpaper = None
            self._wallpaper_mode = None
            self._start_pending()
            return
        self.session.set(stop_wallpaper=True)
        self._wallpaper = None
        self._wallpaper_mode = None
        QTimer.singleShot(1200, lambda: self._finish_stop(proc, generation))

    def _finish_stop(self, proc: subprocess.Popen, generation: int) -> None:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        if generation != self._generation:
            return
        self.session.set(stop_wallpaper=False)
        self._start_pending()

    def _start_pending(self) -> None:
        mode = self._pending_mode
        self._pending_mode = None
        self.session.set(stop_wallpaper=False)
        if mode not in {"video", "paint", "web", "shader"}:
            return
        if self._fails >= 3:
            return
        ensure_data_dir()
        self._log_handle = open(LOG_PATH, "a", encoding="utf-8")
        self._wallpaper = subprocess.Popen(
            [sys.executable, "-m", "deskline.wallpaper_proc"],
            cwd=str(ROOT),
            stdout=self._log_handle,
            stderr=self._log_handle,
            creationflags=CREATE_NO_WINDOW,
        )
        self._wallpaper_mode = mode

    def _sync_awake(self) -> None:
        tools = self.config.section("tools")
        if not tools.get("awake"):
            winutil.clear_awake()
            self._awake_deadline = None
            return
        winutil.set_awake(True, bool(tools.get("awake_screen", True)))
        minutes = int(tools.get("awake_minutes") or 0)
        if minutes <= 0:
            self._awake_deadline = None
        elif self._awake_deadline is None:
            self._awake_deadline = time.monotonic() + minutes * 60

    def _sync_hotkey(self) -> None:
        want = bool(self.config.section("tools").get("hotkey")) and bool(self._hwnd)
        if want and not self._hotkey:
            self._hotkey = winutil.register_topmost_hotkey(self._hwnd)
        elif not want and self._hotkey:
            winutil.unregister_topmost_hotkey(self._hwnd)
            self._hotkey = False

    def _sync_theme(self) -> None:
        windows = self.config.section("windows")
        if not windows.get("schedule"):
            return
        want_light = tweaks.light_wanted(datetime.now(), str(windows.get("light_from")), str(windows.get("dark_from")))
        apps, _system = tweaks.read_theme_light()
        if apps is None or bool(apps) != want_light:
            tweaks.set_theme_light(want_light)

    def _setting_view(self) -> dict:
        wall = self.config.section("wallpaper")
        retro_section = self.config.section("retro")
        windows = self.config.section("windows")
        return {
            "hide_icons": bool(wall.get("hide_icons")),
            "left_taskbar": bool(retro_section.get("left_taskbar")),
            "compact_taskbar": bool(retro_section.get("compact_taskbar")),
            "glass": bool(retro_section.get("glass")),
            "classic_menu": bool(windows.get("classic_menu")),
            "accent": str(windows.get("accent") or ""),
        }

    def _apply_setting_changes(self) -> None:
        current = self._setting_view()
        previous = self._setting_snapshot
        self._setting_snapshot = current
        if current["hide_icons"] != previous["hide_icons"]:
            winutil.toggle_desktop_icons()
        retro_section = self.config.section("retro")
        if current["left_taskbar"] != previous["left_taskbar"]:
            saved = retro.set_left_taskbar(current["left_taskbar"], retro_section.get("saved_align"))
            self.config.update_section("retro", saved_align=saved)
        if current["compact_taskbar"] != previous["compact_taskbar"]:
            saved = retro.set_compact_taskbar(current["compact_taskbar"], retro_section.get("saved_size"))
            self.config.update_section("retro", saved_size=saved)
        if current["glass"] != previous["glass"]:
            saved = retro.set_glass(current["glass"], retro_section.get("saved_transparency"))
            self.config.update_section("retro", saved_transparency=saved)
        if current["classic_menu"] != previous["classic_menu"]:
            tweaks.set_classic_menu(current["classic_menu"])
        if current["accent"] != previous["accent"] and current["accent"]:
            tweaks.set_accent(current["accent"])

    def _tick(self) -> None:
        self._ticks += 1
        if self.config.reload_if_changed():
            self.note_user_edit()
            self._apply_setting_changes()
            self.apply()
        if self._awake_deadline and time.monotonic() >= self._awake_deadline:
            self._awake_deadline = None
            self.config.update_section("tools", awake=False)
            winutil.clear_awake()
            self.changed.emit()
        if self._wallpaper is not None and self._wallpaper.poll() is not None and self._pending_mode is None:
            self._fails += 1
            self._wallpaper = None
            self._wallpaper_mode = None
            if self._fails < 3 and self._wanted_mode() in {"video", "paint", "web", "shader"}:
                self._pending_mode = self._wanted_mode()
                self._start_pending()
        if self._ticks % 30 == 1:
            self._sync_theme()
        self._sync_behavior(not self.session.data.get("pause_effects"))
        self.mixer.poll_power()
        self._sync_game()

    def _sync_game(self) -> None:
        game = self.config.section("game")
        if not game.get("enabled"):
            if self._boosting:
                self._leave_boost()
            self._set_game_status("Game Boost is off.")
            return
        found = winutil.foreground_fullscreen()
        if found and not self._boosting:
            pid, title = found
            try:
                name = psutil.Process(pid).name()
            except (psutil.Error, OSError):
                name = ""
            if name.lower() in SKIP_PROCESSES or pid == os.getpid():
                return
            self._enter_boost(pid, title, name)
        elif not found and self._boosting:
            self._leave_boost()
        elif not self._boosting:
            self._set_game_status("Game Boost is on. Waiting for a fullscreen app.")

    def _enter_boost(self, pid: int, title: str, name: str) -> None:
        game = self.config.section("game")
        scheme = services.active_scheme()
        self._saved_scheme = scheme[0] if scheme else None
        self.session.set(boosting=True, saved_scheme=self._saved_scheme, priority_pid=None)
        notes = []
        if game.get("max_performance"):
            target = services.performance_scheme()
            if target and services.set_scheme(target):
                notes.append("performance plan on")
            else:
                notes.append("high-performance plan is not installed")
        if game.get("priority"):
            if winutil.set_priority(pid, True):
                self._priority_pid = pid
                self.session.set(priority_pid=pid)
                notes.append("priority raised")
            else:
                notes.append("priority unchanged")
        if game.get("pause_effects"):
            self.session.set(pause_effects=True)
            self.apply()
            notes.append("animations paused")
        self._boosting = True
        self._set_game_status(f"Playing: {name or title}. " + ", ".join(notes))

    def _leave_boost(self) -> None:
        if self._saved_scheme:
            services.set_scheme(self._saved_scheme)
        if self._priority_pid:
            winutil.set_priority(self._priority_pid, False)
        self._priority_pid = None
        self._saved_scheme = None
        self._boosting = False
        self.session.set(pause_effects=False, boosting=False, saved_scheme=None, priority_pid=None)
        self.apply()
        if self.config.section("game").get("enabled"):
            self._set_game_status("Game Boost is on. Waiting for a fullscreen app.")
        else:
            self._set_game_status("Game Boost is off.")

    def _set_game_status(self, text: str) -> None:
        if text != self._game_status:
            self._game_status = text
            self.changed.emit()

    def _sync_eq(self) -> None:
        audio = self.config.section("audio")
        enabled = bool(audio.get("eq"))
        bands = tuple(int(item) for item in (audio.get("eq_bands") or []) if isinstance(audio.get("eq_bands"), list))
        key = (enabled, int(audio.get("eq_bass") or 0), int(audio.get("eq_mid") or 0), int(audio.get("eq_treble") or 0), bands)
        if key == self._eq_key:
            return
        self._eq_key = key
        if not enabled and not self._eq_written:
            self._eq_status = (
                "Equalizer APO is not installed. Deskline does not install it."
                if not eqapo.installed()
                else "Equalizer APO is installed. Turn this on to write a bass, mid, and treble block."
            )
            return
        self._eq_status = eqapo.apply_eq(enabled, key[1], key[2], key[3], bands=list(key[4]))
        if enabled and self._eq_status.startswith("Equalizer APO config updated"):
            self._eq_written = True
        if not enabled:
            self._eq_written = False

    def note_user_edit(self) -> None:
        self._fails = 0

    def shutdown(self) -> None:
        self._timer.stop()
        if self._boosting:
            self._leave_boost()
        self.session.set(stop_wallpaper=True, pause_effects=False)
        proc = self._wallpaper
        self._wallpaper = None
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        taskbar_fx.restore()
        if self.taskbar.clear_was_applied():
            winutil.set_taskbar_transparent(False)
        if self._saved_taskbar_state is not None:
            winutil.set_taskbar_appbar_state(int(self._saved_taskbar_state))
        self.hooks.shutdown()
        self.mixer.shutdown()
        self.pointer.shutdown()
        winutil.clear_awake()
        if self._hotkey:
            winutil.unregister_topmost_hotkey(self._hwnd)
        self.cursor.hide()
        self.clock.hide()
        self.monitor.hide()
        self.music.hide()
        self.games.hide()
        self.disk.hide()
        self.net.hide()
        self.notes.hide()
        self.launch.hide()
        self.taskbar.hide()
        if self._log_handle is not None:
            self._log_handle.close()
