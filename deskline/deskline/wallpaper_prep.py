"""Turn a video into a wallpaper package: seamless loop, screen size, 1080p copy, preview."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from deskline.paths import DATA, ensure_data_dir

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LIBRARY = DATA / "wallpapers"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
VIDEO_EXT = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".gif"}
PING_PONG_MAX_SECONDS = 12.0


def screen_pixels() -> tuple[int, int]:
    import ctypes
    from deskline.winutil import enable_dpi_awareness
    enable_dpi_awareness()
    user32 = ctypes.windll.user32
    width = int(user32.GetSystemMetrics(0) or 1920)
    height = int(user32.GetSystemMetrics(1) or 1080)
    return _even(min(width, 3840)), _even(min(height, 2160))


def _even(value: int) -> int:
    value = max(2, int(value))
    return value - (value % 2)


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW, check=False)


def probe(path: str) -> dict:
    completed = _run([_ffmpeg(), "-hide_banner", "-i", path])
    text = f"{completed.stderr}\n{completed.stdout}"
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    size_match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if duration_match is None or size_match is None:
        raise RuntimeError("This file does not look like a video Deskline can process.")
    duration = int(duration_match.group(1)) * 3600 + int(duration_match.group(2)) * 60 + float(duration_match.group(3))
    fps = float(fps_match.group(1)) if fps_match else 30.0
    return {
        "duration": duration,
        "width": int(size_match.group(1)),
        "height": int(size_match.group(2)),
        "fps": fps,
        "frames": int(duration * fps),
    }


def _encode(source: str, destination: Path, width: int, height: int, ping_pong: bool, on_progress) -> None:
    width, height = _even(width), _even(height)
    if ping_pong:
        graph = (
            f"[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,"
            f"fps=30,scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p[v]"
        )
    else:
        graph = (
            f"[0:v]fps=30,scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p[v]"
        )
    command = [
        _ffmpeg(), "-y", "-hide_banner", "-i", source,
        "-filter_complex", graph, "-map", "[v]", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats",
        str(destination),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=CREATE_NO_WINDOW,
    )
    assert process.stdout is not None
    info = probe(source)
    total_s = max(0.1, info["duration"] * (2 if ping_pong else 1))
    for line in process.stdout:
        text = line.strip()
        # ffmpeg's out_time_ms field is microseconds.
        if text.startswith("out_time_ms="):
            try:
                done_s = int(text.split("=", 1)[1]) / 1_000_000
            except ValueError:
                continue
            on_progress(min(0.99, done_s / total_s))
    stderr = process.stderr.read() if process.stderr else ""
    code = process.wait()
    if code != 0 or not destination.is_file():
        tail = "\n".join(stderr.splitlines()[-8:])
        raise RuntimeError(tail or "ffmpeg could not build the wallpaper.")


def _preview(video: Path, destination: Path) -> None:
    completed = _run([
        _ffmpeg(), "-y", "-ss", "0.4", "-i", str(video),
        "-frames:v", "1", "-vf", "scale=480:-2", str(destination),
    ])
    if completed.returncode != 0 or not destination.is_file():
        raise RuntimeError("Could not make a preview image.")


def list_library() -> list[dict]:
    if not LIBRARY.is_dir():
        return []
    items = []
    for folder in LIBRARY.iterdir():
        meta_path = folder / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        meta["folder"] = str(folder)
        meta["preview"] = str(folder / "preview.jpg")
        items.append(meta)
    items.sort(key=lambda item: str(item.get("created") or ""), reverse=True)
    return items


def media_for(meta: dict, screen_height: int) -> tuple[str, str]:
    folder = Path(str(meta.get("folder") or ""))
    if meta.get("kind") == "image":
        image = folder / str(meta.get("file") or "")
        return "image", str(image)
    light = folder / "video_1080.mp4"
    full = folder / "video.mp4"
    if screen_height <= 1200 and light.is_file():
        return "video", str(light)
    if full.is_file():
        return "video", str(full)
    return "video", str(light)


def resolve(section: dict) -> tuple[str, str, str]:
    """Return kind, path, display name for the wallpaper that should play."""
    active = str(section.get("active_id") or "")
    height = screen_pixels()[1]
    for item in list_library():
        if str(item.get("id")) == active:
            kind, path = media_for(item, height)
            return kind, path, str(item.get("name") or Path(path).name)
    path = str(section.get("path") or "")
    if path and os.path.isfile(path):
        kind = "image" if Path(path).suffix.lower() in IMAGE_EXT else "video"
        return kind, path, Path(path).name
    return "none", "", ""


def needs_paint(section: dict) -> bool:
    overlay = str(section.get("overlay") or "none")
    return int(section.get("blur") or 0) > 0 or int(section.get("brightness") or 0) < 0 or overlay not in {"", "none"}


def playlist(section: dict) -> list[tuple[str, str, str]]:
    height = screen_pixels()[1]
    rows = []
    for item in list_library():
        kind, path = media_for(item, height)
        if kind == "video" and os.path.isfile(path):
            rows.append((str(item.get("id")), str(item.get("name") or ""), path))
    return rows


def prepare(source: str, on_progress=None) -> dict:
    """Build a library entry. on_progress receives a short status string."""
    def report(message: str) -> None:
        if on_progress:
            on_progress(message)

    source_path = Path(source)
    if not source_path.is_file():
        raise RuntimeError("That file is not there anymore.")
    ensure_data_dir()
    LIBRARY.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    entry_id = uuid.uuid4().hex[:10]
    folder = LIBRARY / entry_id
    folder.mkdir(parents=True)
    try:
        if suffix in IMAGE_EXT:
            return _prepare_image(source_path, folder, entry_id, report)
        if suffix not in VIDEO_EXT:
            raise RuntimeError("Use a video, a GIF, or a still image.")
        return _prepare_video(source_path, folder, entry_id, report)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def _prepare_image(source: Path, folder: Path, entry_id: str, report) -> dict:
    report("Saving the still image…")
    target_name = "image" + source.suffix.lower()
    shutil.copy2(source, folder / target_name)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError("Could not read that image.")
    image.scaled(480, 270, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(
        str(folder / "preview.jpg"), "JPG", 85,
    )
    meta = {
        "id": entry_id,
        "kind": "image",
        "name": source.stem,
        "file": target_name,
        "source": str(source),
        "width": image.width(),
        "height": image.height(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta["folder"] = str(folder)
    meta["preview"] = str(folder / "preview.jpg")
    report("Ready.")
    return meta


def _prepare_video(source: Path, folder: Path, entry_id: str, report) -> dict:
    report("Reading the video…")
    info = probe(str(source))
    screen_w, screen_h = screen_pixels()
    ping_pong = info["duration"] <= PING_PONG_MAX_SECONDS and info["duration"] > 0.4
    report("Building a screen-sized loop…" if ping_pong else "Fitting the video to the screen…")

    def full_progress(fraction: float) -> None:
        report(f"Screen copy {int(fraction * 100)}%")

    _encode(str(source), folder / "video.mp4", screen_w, screen_h, ping_pong, full_progress)
    has_1080 = screen_h > 1200
    if has_1080:
        report("Building the lighter 1080p copy…")
        light_w = _even(int(screen_w * 1080 / screen_h))
        _encode(str(source), folder / "video_1080.mp4", light_w, 1080, ping_pong, lambda fraction: report(f"1080p copy {int(fraction * 100)}%"))
    report("Making the preview…")
    _preview(folder / "video.mp4", folder / "preview.jpg")
    frames_out = info["frames"] * (2 if ping_pong else 1)
    meta = {
        "id": entry_id,
        "kind": "video",
        "name": source.stem,
        "source": str(source),
        "width": screen_w,
        "height": screen_h,
        "fps": 30.0,
        "duration": round(info["duration"] * (2 if ping_pong else 1), 2),
        "frames_in": info["frames"],
        "frames_out": frames_out,
        "ping_pong": ping_pong,
        "has_1080": has_1080,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta["folder"] = str(folder)
    meta["preview"] = str(folder / "preview.jpg")
    report("Ready.")
    return meta


def delete_entry(entry_id: str) -> None:
    folder = LIBRARY / entry_id
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
