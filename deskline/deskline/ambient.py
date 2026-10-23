"""Layered generated ambience and a laptop plug or unplug chime."""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect

from deskline.sounds import sound_path

LAYERS = ("rain", "wind", "birds", "city", "thunder")


class _Power(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def ac_line() -> int:
    status = _Power()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return 255
    return int(status.ACLineStatus)


class AmbientMixer(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._players: dict[str, tuple[QMediaPlayer, QAudioOutput]] = {}
        for name in LAYERS:
            player = QMediaPlayer(self)
            output = QAudioOutput(self)
            player.setAudioOutput(output)
            player.setLoops(QMediaPlayer.Loops.Infinite)
            player.setSource(QUrl.fromLocalFile(sound_path(name)))
            self._players[name] = (player, output)
        self.plug = QSoundEffect(self)
        self.unplug = QSoundEffect(self)
        self.plug.setSource(QUrl.fromLocalFile(sound_path("plug")))
        self.unplug.setSource(QUrl.fromLocalFile(sound_path("unplug")))
        self._chime = False
        self._ac: int | None = None

    def apply(self, audio: dict, paused: bool) -> None:
        for name, (player, output) in self._players.items():
            volume = 0.0 if paused else max(0.0, min(1.0, int(audio.get(name) or 0) / 100))
            output.setVolume(volume)
            playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            if volume > 0 and not playing:
                player.play()
            elif volume <= 0 and playing:
                player.stop()
        self._chime = bool(audio.get("plug_chime")) and not paused
        if self._ac is None:
            self._ac = ac_line()

    def poll_power(self) -> None:
        if not self._chime:
            self._ac = ac_line()
            return
        current = ac_line()
        if self._ac in (0, 1) and current in (0, 1) and current != self._ac:
            (self.plug if current == 1 else self.unplug).play()
        self._ac = current

    def shutdown(self) -> None:
        for player, _output in self._players.values():
            player.stop()
