"""Read the Windows now-playing session when the WinRT bindings are installed."""

from __future__ import annotations

import asyncio
import threading

_lock = threading.Lock()
_running = False
_cache = {"title": "", "artist": "", "detail": "Play something to see it here."}


def snapshot() -> dict:
    with _lock:
        return dict(_cache)


def refresh() -> None:
    global _running
    with _lock:
        if _running:
            return
        _running = True
    threading.Thread(target=_work, daemon=True).start()


def _work() -> None:
    global _running
    try:
        title, artist, detail = asyncio.run(_read())
        with _lock:
            _cache.update(title=title, artist=artist, detail=detail)
    except Exception as exc:
        with _lock:
            _cache.update(title="", artist="", detail=str(exc))
    finally:
        with _lock:
            _running = False


async def _read() -> tuple[str, str, str]:
    manager_type = _manager_type()
    if manager_type is None:
        return "", "", "Now playing needs the Windows media bindings. Install them with pip if you want this widget."
    manager = await manager_type.request_async()
    session = manager.get_current_session()
    if session is None:
        return "", "", "Nothing is playing."
    props = await session.try_get_media_properties_async()
    title = str(getattr(props, "title", "") or "")
    artist = str(getattr(props, "artist", "") or "")
    if not title and not artist:
        return "", "", "Nothing is playing."
    return title, artist, ""


def _manager_type():
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        return GlobalSystemMediaTransportControlsSessionManager
    except ImportError:
        pass
    try:
        from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
        return GlobalSystemMediaTransportControlsSessionManager
    except ImportError:
        return None
