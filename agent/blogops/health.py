"""상태 점검 (get_system_health). 문제가 있으면 problems에 담는다."""
from __future__ import annotations

import shutil
import urllib.request
from datetime import datetime
from pathlib import Path

from . import records
from .config import KST, Config
from .store import Store

DISK_MIN_FREE_PCT = 10
CPU_TEMP_WARN_C = 75


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def check(config: Config, store: Store) -> dict:
    problems = []
    disk = shutil.disk_usage(config.root)
    disk_free_pct = round(disk.free / disk.total * 100, 1)
    if disk_free_pct < DISK_MIN_FREE_PCT:
        problems.append(f"디스크 여유가 {disk_free_pct}%다")

    temp = _read("/sys/class/thermal/thermal_zone0/temp")
    cpu_temp_c = round(int(temp) / 1000, 1) if temp and temp.isdigit() else None
    if cpu_temp_c and cpu_temp_c >= CPU_TEMP_WARN_C:
        problems.append(f"CPU 온도가 {cpu_temp_c}°C다")

    uptime = _read("/proc/uptime")
    meminfo = dict(line.split(":", 1) for line in (_read("/proc/meminfo") or "").splitlines() if ":" in line)
    mem = {k: round(int(meminfo[k].split()[0]) / 1024 / 1024, 2) for k in ("MemTotal", "MemAvailable") if k in meminfo}

    base = records.site_base_url(config)
    try:
        req = urllib.request.Request(base + "/", headers={"User-Agent": "Huninn-blogops/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            site_status = resp.status
    except OSError as e:
        site_status = getattr(e, "code", 0)
    if site_status != 200:
        problems.append(f"사이트가 응답하지 않는다: {base}/ → {site_status}")

    index = config.site_dir / "public" / "index.html"
    last_build = datetime.fromtimestamp(index.stat().st_mtime, KST).isoformat(timespec="seconds") if index.exists() else None

    drafts = store.list_drafts()
    by_status: dict[str, int] = {}
    for d in drafts:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    # 보류는 시스템 문제가 아니다. 보류될 때 이미 알렸고, 다른 글감으로 계속 쓴다
    held = [d["draft_id"] for d in drafts if d["status"] == "held"]

    return {"ok": not problems, "problems": problems, "now": config.now().isoformat(timespec="seconds"),
            "disk_free_pct": disk_free_pct, "cpu_temp_c": cpu_temp_c,
            "uptime_hours": round(float(uptime.split()[0]) / 3600, 1) if uptime else None,
            "memory_gb": {"total": mem.get("MemTotal"), "available": mem.get("MemAvailable")},
            "site": {"url": base, "status": site_status, "last_build": last_build},
            "drafts": by_status, "held": held}
