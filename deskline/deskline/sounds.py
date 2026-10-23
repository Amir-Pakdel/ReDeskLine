"""Generated clicks, ambience, and chimes. No borrowed sound packs."""

from __future__ import annotations

import math
import random
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from deskline.paths import DATA, ensure_data_dir

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def sound_path(name: str) -> str:
    ensure_data_dir()
    folder = DATA / "sounds"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.wav"
    if not path.is_file():
        if name == "mouse":
            _tone(path, 700, 40)
        elif name == "scape":
            _noise(path, 2.0)
        elif name == "rain":
            _rain(path)
        elif name == "wind":
            _noise(path, 4.0, 0.995, 0.008, 5000)
        elif name == "birds":
            _birds(path)
        elif name == "city":
            _noise(path, 4.0, 0.99, 0.015, 3500)
        elif name == "thunder":
            _thunder(path)
        elif name == "plug":
            _sweep(path, 520, 880, 180)
        elif name == "unplug":
            _sweep(path, 660, 280, 180)
        else:
            _tone(path, 1600, 28)
    return str(path)


def install_upload(source: str, slot: str) -> str:
    """Copy or convert a user click into a wav Deskline can play."""
    ensure_data_dir()
    folder = DATA / "sounds"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"upload-{slot}.wav"
    suffix = Path(source).suffix.lower()
    if suffix == ".wav":
        shutil.copyfile(source, dest)
        return str(dest)
    from deskline.wallpaper_prep import _ffmpeg
    result = subprocess.run(
        [_ffmpeg(), "-y", "-i", source, "-ac", "1", "-ar", "44100", str(dest)],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )
    if result.returncode != 0 or not dest.is_file():
        raise RuntimeError("Could not convert that file to a click sound.")
    return str(dest)


def _tone(path, frequency: float, milliseconds: int) -> None:
    rate = 44100
    count = int(rate * milliseconds / 1000)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            envelope = (1 - index / count) ** 2
            sample = int(math.sin(2 * math.pi * frequency * index / rate) * 12000 * envelope)
            frames += struct.pack("<h", sample)
        handle.writeframes(frames)


def _noise(path, seconds: float, keep: float = 0.98, drive: float = 0.02, gain: int = 8000) -> None:
    rate = 22050
    count = int(rate * seconds)
    value = 0.0
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for _ in range(count):
            value = value * keep + random.uniform(-1, 1) * drive
            frames += struct.pack("<h", int(max(-1, min(1, value)) * gain))
        handle.writeframes(frames)


def _write(path, samples: list[int], rate: int = 22050) -> None:
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", max(-32767, min(32767, int(sample)))) for sample in samples))


def _sweep(path, start: float, end: float, milliseconds: int) -> None:
    rate = 44100
    count = int(rate * milliseconds / 1000)
    samples = []
    phase = 0.0
    for index in range(count):
        mix = index / max(1, count - 1)
        frequency = start + (end - start) * mix
        phase += 2 * math.pi * frequency / rate
        envelope = math.sin(math.pi * mix)
        samples.append(int(math.sin(phase) * 14000 * envelope))
    _write(path, samples, rate)


def _rain(path) -> None:
    rate = 22050
    count = rate * 3
    value = 0.0
    samples = []
    for index in range(count):
        value = value * 0.2 + random.uniform(-1, 1) * 0.8
        drop = 1.0 if random.random() < 0.004 else 0.35
        samples.append(int(max(-1, min(1, value)) * 4000 * drop))
    _write(path, samples, rate)


def _birds(path) -> None:
    rate = 22050
    count = rate * 4
    samples = [0] * count
    for start, frequency in ((rate // 5, 2400), (rate * 2, 3100)):
        length = int(rate * 0.18)
        for index in range(length):
            envelope = math.sin(math.pi * index / length)
            wobble = math.sin(2 * math.pi * 18 * index / rate)
            samples[start + index] += int(math.sin(2 * math.pi * (frequency + wobble * 80) * index / rate) * 9000 * envelope)
    _write(path, samples, rate)


def _thunder(path) -> None:
    rate = 22050
    count = rate * 3
    value = 0.0
    samples = []
    for index in range(count):
        value = value * 0.97 + random.uniform(-1, 1) * 0.08
        envelope = math.exp(-index / (rate * 0.7))
        samples.append(int(max(-1, min(1, value)) * 18000 * envelope))
    _write(path, samples, rate)
