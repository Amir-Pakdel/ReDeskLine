"""Optional system-wide EQ through an already installed Equalizer APO config."""

from __future__ import annotations

from pathlib import Path

BEGIN = "# Deskline EQ begin"
END = "# Deskline EQ end"
DEFAULT_CONFIG = Path(r"C:\Program Files\EqualizerAPO\config\config.txt")


def installed(path: Path | None = None) -> bool:
    return (path or DEFAULT_CONFIG).is_file()


_FREQS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)


def apply_eq(enabled: bool, bass: int, mid: int, treble: int, path: Path | None = None, bands: list[int] | None = None) -> str:
    target = path or DEFAULT_CONFIG
    if not target.is_file():
        return "Equalizer APO is not installed. Deskline does not install it."
    bass = max(-12, min(12, int(bass)))
    mid = max(-12, min(12, int(mid)))
    treble = max(-12, min(12, int(treble)))
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Could not read the Equalizer APO config: {exc}"
    body = _strip(text).rstrip() + "\n"
    if enabled:
        body += f"{BEGIN}\nPreamp: 0 dB\n{eq_line(bass, mid, treble, bands)}\n{END}\n"
    try:
        target.write_text(body, encoding="utf-8")
    except OSError as exc:
        return f"Could not write the Equalizer APO config. Run Deskline as the user who installed it, or edit config.txt yourself. {exc}"
    if enabled:
        return "Equalizer APO config updated. Restart an app if it was already playing audio."
    return "Deskline EQ block removed from the Equalizer APO config."


def eq_line(bass: int, mid: int, treble: int, bands: list[int] | None) -> str:
    values = [int(item) for item in bands] if bands else []
    if len(values) == len(_FREQS) and any(values):
        parts = [f"{freq} {max(-12, min(12, gain)):.1f}" for freq, gain in zip(_FREQS, values)]
        return "GraphicEQ: " + "; ".join(parts)
    bass = max(-12, min(12, int(bass)))
    mid = max(-12, min(12, int(mid)))
    treble = max(-12, min(12, int(treble)))
    return f"GraphicEQ: 60 {bass:.1f}; 250 {bass / 2:.1f}; 1000 {mid:.1f}; 4000 {treble / 2:.1f}; 8000 {treble:.1f}"


def _strip(text: str) -> str:
    while True:
        start = text.find(BEGIN)
        end = text.find(END)
        if start < 0 or end < start:
            return text
        end = end + len(END)
        if end < len(text) and text[end] == "\n":
            end += 1
        text = text[:start] + text[end:]
