"""상태 점검 (get_system_health). 문제가 있으면 problems에 담는다.

problems는 사이클을 멈춘다(prompt.md 1번: 알리고 발행·글쓰기를 건너뛴다). 글과 발행에는 지장이 없지만
운영자가 알아야 하는 일(디스코드 봇이 멈춤, Pi 상태 파일이 갱신되지 않음)은 notices에 담는다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

from . import records, status
from .config import KST, Config
from .store import Store

DISK_MIN_FREE_PCT = 10
CPU_TEMP_WARN_C = 75
STATUS_STALE_MIN = 30  # 상태 띠가 "갱신 멈춤"을 띄우는 기준과 같다 (site status-script.html)
BOT_UNIT = "huninn-bot.service"


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def unit_state(unit: str) -> str:
    """systemd 유닛 상태(active, inactive, failed …). 알 수 없으면 unknown."""
    try:
        out = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def status_file_age_min(config: Config, path: Path = status.DEFAULT_PATH) -> float | None:
    """Pi 상태 파일(status.json)의 updated가 몇 분 전인지. 파일이 없거나 읽지 못하면 None."""
    try:
        updated = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["updated"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return round((config.now() - updated).total_seconds() / 60, 1)


def check(config: Config, store: Store, *, bot_state=unit_state, status_age=status_file_age_min) -> dict:
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

    notices = []
    bot = bot_state(BOT_UNIT)
    if bot not in ("active", "unknown"):
        notices.append(f"디스코드 봇이 멈춰 있다({BOT_UNIT}: {bot}). 승인 버튼이 듣지 않으니 review 명령으로 승인해야 한다")
    age = status_age(config)
    if age is None:
        notices.append("Pi 상태 파일(status.json)이 없다. 상태 띠가 \"운영 준비 중\"만 보인다 (huninn-status.timer)")
    elif age > STATUS_STALE_MIN:
        notices.append(f"Pi 상태 파일이 {age:.0f}분째 갱신되지 않았다. 상태 띠가 \"갱신 멈춤\"을 띄운다 (huninn-status.timer)")

    return {"ok": not problems, "problems": problems, "notices": notices,
            "now": config.now().isoformat(timespec="seconds"),
            "disk_free_pct": disk_free_pct, "cpu_temp_c": cpu_temp_c,
            "uptime_hours": round(float(uptime.split()[0]) / 3600, 1) if uptime else None,
            "memory_gb": {"total": mem.get("MemTotal"), "available": mem.get("MemAvailable")},
            "site": {"url": base, "status": site_status, "last_build": last_build},
            "services": {"bot": bot, "status_file_age_min": age},
            "drafts": by_status, "held": held}
