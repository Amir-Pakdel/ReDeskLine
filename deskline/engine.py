"""Runs Deskline effects without a second settings window."""

from __future__ import annotations

import sys
import traceback

from deskline.config import log


def _hook(exc_type, exc, tb) -> None:
    log("".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _hook

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from deskline import winutil
from deskline.config import Config
from deskline.paths import ensure_data_dir
from deskline.runtime import Runtime


def main() -> None:
    log("engine: start")
    winutil.enable_dpi_awareness()
    if not winutil.acquire_single_instance():
        log("engine: already running")
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    runtime = Runtime(Config())
    log("engine: running")

    def watch_stop() -> None:
        stop = ensure_data_dir() / "engine.stop"
        if not stop.exists():
            return
        try:
            stop.unlink()
        except OSError:
            pass
        runtime.shutdown()
        app.quit()

    timer = QTimer()
    timer.timeout.connect(watch_stop)
    timer.start(250)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
