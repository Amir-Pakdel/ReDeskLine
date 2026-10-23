"""Measurements and file cleanup. No Qt imports, so a worker thread stays light."""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import psutil

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
HASH_SECONDS = 0.7
TEMP_MIN_AGE = timedelta(minutes=15)


def format_bytes(size: float) -> str:
    if size < 0:
        size = 0
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit in {"B", "KB"}:
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size:.0f} B"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _run(args: list[str], timeout: float = 20) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout or ""


def power_schemes() -> list[tuple[str, str, bool]]:
    schemes = []
    for line in _run(["powercfg", "/list"]).splitlines():
        if ":" not in line or "power scheme guid" not in line.lower() and "GUID" not in line:
            # English and localized lines both contain a GUID.
            pass
        start = line.find("GUID: ")
        if start < 0:
            continue
        guid = line[start + 6:start + 42].strip()
        name = line.split("(", 1)[-1].rsplit(")", 1)[0].strip() if "(" in line else guid
        active = "*" in line
        if len(guid) >= 36:
            schemes.append((guid[:36], name, active))
    return schemes


def active_scheme() -> tuple[str, str] | None:
    for guid, name, active in power_schemes():
        if active:
            return guid, name
    return None


def set_scheme(guid: str) -> bool:
    if not guid:
        return False
    completed = subprocess.run(
        ["powercfg", "/setactive", guid],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return completed.returncode == 0


def performance_scheme() -> str | None:
    schemes = power_schemes()
    by_guid = {guid.lower(): guid for guid, _name, _active in schemes}
    for candidate in (ULTIMATE, HIGH_PERFORMANCE):
        if candidate in by_guid:
            return by_guid[candidate]
    for guid, name, _active in schemes:
        lowered = name.casefold()
        if "high" in lowered or "ultimate" in lowered or "höchst" in lowered or "حداکثر" in lowered:
            return guid
    return None


def duplicate_high_performance() -> bool:
    completed = subprocess.run(
        ["powercfg", "-duplicatescheme", HIGH_PERFORMANCE],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return completed.returncode == 0


def startup_names() -> list[str]:
    import winreg

    names: list[str] = []
    roots = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for root, path in roots:
        try:
            with winreg.OpenKey(root, path) as key:
                count = winreg.QueryInfoKey(key)[1]
                for index in range(count):
                    names.append(winreg.EnumValue(key, index)[0])
        except OSError:
            continue
    startup = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    if startup.is_dir():
        for entry in startup.iterdir():
            if entry.suffix.lower() in {".lnk", ".exe", ".bat", ".cmd"}:
                names.append(entry.stem)
    return names


def hardware_names() -> dict[str, str]:
    script = (
        "$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "$gpu = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '; "
        "$os = (Get-CimInstance Win32_OperatingSystem).Caption; "
        "[pscustomobject]@{cpu=$cpu.Name; cores=$cpu.NumberOfCores; threads=$cpu.NumberOfLogicalProcessors; gpu=$gpu; os=$os} "
        "| ConvertTo-Json -Compress"
    )
    raw = _run(["powershell", "-NoProfile", "-Command", script], timeout=25)
    try:
        import json
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    return {
        "cpu": str(parsed.get("cpu") or platform.processor() or "Unknown CPU"),
        "cores": str(parsed.get("cores") or psutil.cpu_count(logical=False) or "?"),
        "threads": str(parsed.get("threads") or psutil.cpu_count(logical=True) or "?"),
        "gpu": str(parsed.get("gpu") or "Unknown GPU"),
        "os": str(parsed.get("os") or platform.platform()),
    }


def machine_facts() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    scheme = active_scheme()
    return {
        "memory_total": memory.total,
        "memory_used": memory.used,
        "memory_percent": memory.percent,
        "disk_total": disk.total,
        "disk_free": disk.free,
        "disk_percent": disk.percent,
        "uptime": time.time() - psutil.boot_time(),
        "power": scheme[1] if scheme else "Unknown",
        "power_guid": scheme[0] if scheme else "",
        "startup": startup_names(),
        "logical_cpus": psutil.cpu_count(logical=True) or 1,
    }


def _hash_for(seconds: float) -> int:
    block = bytes(256 * 1024)
    end = time.perf_counter() + seconds
    count = 0
    while time.perf_counter() < end:
        hashlib.sha256(block).digest()
        count += 1
    return count


def _hash_megabytes_per_second(count: int, seconds: float) -> float:
    return (count * 0.25) / max(seconds, 0.001)


def run_benchmark() -> dict:
    single_count = _hash_for(HASH_SECONDS)
    single = _hash_megabytes_per_second(single_count, HASH_SECONDS)
    workers = max(1, psutil.cpu_count(logical=True) or 1)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        counts = list(pool.map(lambda _i: _hash_for(HASH_SECONDS), range(workers)))
    multi_elapsed = time.perf_counter() - started
    multi = (sum(counts) * 0.25) / max(multi_elapsed, 0.001)

    size = 48 * 1024 * 1024
    source = bytearray(size)
    target = bytearray(size)
    copies = 0
    memory_started = time.perf_counter()
    while time.perf_counter() - memory_started < 0.45:
        target[:] = source
        copies += 1
    memory_elapsed = time.perf_counter() - memory_started
    memory_gb = (copies * size) / memory_elapsed / 1e9

    blob = b"\0" * (32 * 1024 * 1024)
    directory = Path(os.environ.get("TEMP", "."))
    sample = directory / "deskline-disk-sample.bin"
    write_mb = 0.0
    read_mb = 0.0
    try:
        write_started = time.perf_counter()
        with sample.open("wb") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
        write_mb = len(blob) / (time.perf_counter() - write_started) / 1e6
        read_started = time.perf_counter()
        with sample.open("rb") as handle:
            while handle.read(1024 * 1024):
                pass
        read_mb = len(blob) / (time.perf_counter() - read_started) / 1e6
    finally:
        try:
            sample.unlink(missing_ok=True)
        except OSError:
            pass

    busiest = _busiest_processes()
    return {
        "at": datetime.now().strftime("%d.%m. %H:%M"),
        "cpu1": round(single),
        "cpu_all": round(multi),
        "memory": round(memory_gb, 1),
        "read": round(read_mb),
        "write": round(write_mb),
        "busiest": busiest,
    }


def _busiest_processes() -> list[dict]:
    names = []
    for proc in psutil.process_iter(["name"]):
        try:
            proc.cpu_percent(None)
            names.append(proc)
        except (psutil.Error, OSError):
            continue
    time.sleep(0.35)
    ranked = []
    ignored = {"system idle process", "system", "registry", "memory compression", "secure system"}
    for proc in names:
        try:
            name = proc.name()
            if not name or name.lower() in ignored:
                continue
            ranked.append((proc.cpu_percent(None), proc.memory_info().rss, name))
        except (psutil.Error, OSError):
            continue
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        {"name": name, "cpu": round(cpu, 1), "memory": rss}
        for cpu, rss, name in ranked[:3]
        if name
    ]


def _folder_size(root: Path, min_age: timedelta | None = None) -> tuple[int, list[Path]]:
    files: list[Path] = []
    total = 0
    if not root.exists():
        return 0, files
    cutoff = time.time() - min_age.total_seconds() if min_age else None
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if not Path(dirpath, name).is_symlink()]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if path.is_symlink():
                    continue
                stat = path.stat()
            except OSError:
                continue
            if cutoff is not None and stat.st_mtime > cutoff:
                continue
            total += stat.st_size
            if len(files) < 200_000:
                files.append(path)
    return total, files


def _glob_size(root: Path, pattern: str) -> tuple[int, list[Path]]:
    files = []
    total = 0
    if not root.exists():
        return 0, files
    for path in root.glob(pattern):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
                files.append(path)
        except OSError:
            continue
    return total, files


def recycle_bin_size() -> int:
    import ctypes

    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("i64Size", ctypes.c_longlong),
            ("i64NumItems", ctypes.c_longlong),
        ]

    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
    shell32 = ctypes.windll.shell32
    shell32.SHQueryRecycleBinW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(SHQUERYRBINFO)]
    shell32.SHQueryRecycleBinW.restype = ctypes.c_long
    if shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0
    return max(0, int(info.i64Size))


def empty_recycle_bin() -> bool:
    import ctypes

    shell32 = ctypes.windll.shell32
    shell32.SHEmptyRecycleBinW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
    shell32.SHEmptyRecycleBinW.restype = ctypes.c_long
    # No confirmation dialog, no progress window, no sound. The app already asked.
    flags = 0x00000001 | 0x00000002 | 0x00000004
    return shell32.SHEmptyRecycleBinW(None, None, flags) == 0


def scan_cleanup() -> list[dict]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    temp = Path(os.environ.get("TEMP", ""))
    categories = []

    def add(key: str, title: str, detail: str, total: int, files: list[Path], recycle: bool = False):
        categories.append({
            "id": key,
            "title": title,
            "detail": detail,
            "bytes": total,
            "files": files,
            "recycle": recycle,
        })

    temp_bytes, temp_files = _folder_size(temp, TEMP_MIN_AGE)
    add("temp", "Temporary files", "Leftovers older than 15 minutes. Files still open are skipped.", temp_bytes, temp_files)
    dump_bytes, dump_files = _folder_size(local / "CrashDumps")
    add("dumps", "Crash dumps", "Memory dumps from crashed apps.", dump_bytes, dump_files)
    report_bytes = 0
    report_files: list[Path] = []
    for folder in ("ReportArchive", "ReportQueue"):
        size, files = _folder_size(local / "Microsoft" / "Windows" / "WER" / folder)
        report_bytes += size
        report_files.extend(files)
    add("reports", "Error reports", "Windows error reports that were already sent.", report_bytes, report_files)
    thumb_bytes, thumb_files = _glob_size(local / "Microsoft" / "Windows" / "Explorer", "thumbcache_*.db")
    add("thumbs", "Thumbnail cache", "Preview pictures in File Explorer. Windows rebuilds them.", thumb_bytes, thumb_files)
    add("recycle", "Recycle Bin", "Files you already deleted.", recycle_bin_size(), [], recycle=True)
    return categories


def network_report() -> dict:
    import re
    gateway = ""
    route = _run(["powershell", "-NoProfile", "-Command",
                  "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop"])
    gateway = route.strip().splitlines()[-1].strip() if route.strip() else ""
    stats = []
    for name, info in psutil.net_if_stats().items():
        if info.isup and info.speed:
            stats.append(f"{name} · {info.speed} Mbit/s")
    link = stats[0] if stats else "No active adapter reported a speed"

    def ping(host: str) -> dict:
        text = _run(["ping", "-n", "4", "-w", "1000", host])
        loss = re.search(r"(\d+)%\s+loss", text) or re.search(r"(\d+)%\s+Verlust", text) or re.search(r"(\d+)%", text)
        average = re.search(r"Average\s*=\s*(\d+)ms", text) or re.search(r"Mittelwert\s*=\s*(\d+)ms", text) or re.search(r"Average\s*=\s*(\d+)", text)
        times = [int(item) for item in re.findall(r"time[=<](\d+)ms", text, flags=re.I)]
        if not times:
            times = [int(item) for item in re.findall(r"Zeit[=<](\d+)ms", text)]
        jitter = 0
        if len(times) >= 2:
            jitter = max(times) - min(times)
        lost = int(loss.group(1)) if loss else 100
        avg = int(average.group(1)) if average else (round(sum(times) / len(times)) if times else None)
        return {"ms": avg, "jitter": jitter, "loss": lost}

    router = ping(gateway) if gateway else {"ms": None, "jitter": 0, "loss": 100}
    return {
        "link": link,
        "gateway": gateway or "unknown",
        "router": router,
        "cloudflare": ping("1.1.1.1"),
        "google": ping("8.8.8.8"),
    }


def driver_report() -> dict:
    script = (
        "$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1; "
        "$date = if ($gpu.DriverDate) { $gpu.DriverDate.ToString('yyyyMMdd') } else { '' }; "
        "$bad = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -notin 0,22 } | Select-Object -ExpandProperty Name); "
        "[pscustomobject]@{name=$gpu.Name; version=$gpu.DriverVersion; date=$date; problems=($bad -join '|')} | ConvertTo-Json -Compress"
    )
    raw = _run(["powershell", "-NoProfile", "-Command", script], timeout=30)
    try:
        import json
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    date_text = str(parsed.get("date") or "")
    months = None
    digits = "".join(ch for ch in date_text if ch.isdigit())
    if len(digits) >= 8:
        from datetime import datetime
        try:
            made = datetime(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
            months = max(0, (datetime.now() - made).days // 30)
        except ValueError:
            months = None
    problems = [item for item in str(parsed.get("problems") or "").split("|") if item]
    name = str(parsed.get("name") or "Graphics adapter")
    vendor = "windows"
    lowered = name.lower()
    if "nvidia" in lowered:
        vendor = "nvidia"
    elif "amd" in lowered or "radeon" in lowered:
        vendor = "amd"
    elif "intel" in lowered:
        vendor = "intel"
    return {
        "name": name,
        "version": str(parsed.get("version") or "unknown"),
        "months": months,
        "problems": problems,
        "vendor": vendor,
    }


def delete_category(category: dict) -> tuple[int, int]:
    """Return (bytes removed, files skipped because they were in use)."""
    if category.get("recycle"):
        before = int(category.get("bytes") or 0)
        ok = empty_recycle_bin()
        return (before, 0) if ok else (0, 1)
    removed = 0
    skipped = 0
    for path in category.get("files") or []:
        try:
            size = path.stat().st_size
            path.unlink()
            removed += size
        except OSError:
            skipped += 1
    return removed, skipped
