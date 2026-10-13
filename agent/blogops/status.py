"""Pi 상태 파일 (docs/status.md). 상태 띠와 통계 탭이 브라우저에서 읽는 status.json을 쓴다.

타이머(huninn-status.timer)가 5분마다 한 번 실행해 /run/huninn/status.json(tmpfs)에 쓴다.
읽기만 하고, 공개해도 되는 값(CPU 온도, 메모리, 디스크 여유, 가동 시간)만 담는다.
읽지 못한 값은 필드를 빼서 화면에서 사라지게 한다. 연속 무인 운영일과 오늘 비용은 개입 기록과
환율이 정해진 뒤에 더한다(site/README.md의 status.json 형식).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from .config import KST
from .fileio import write_atomic

DEFAULT_PATH = Path("/run/huninn/status.json")  # RAM이라 SD카드에 쓰지 않는다. Caddy가 /status.json으로 내준다
THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")
MEMINFO = Path("/proc/meminfo")
UPTIME = Path("/proc/uptime")
GIB = 1024 ** 3


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def cpu_temp_c(path: Path = THERMAL) -> float | None:
    raw = _read(path)
    return round(int(raw) / 1000, 1) if raw and raw.isdigit() else None


def memory_gb(path: Path = MEMINFO) -> tuple[float, float] | None:
    """(사용 중, 전체) GB. 사용 중은 전체에서 사용 가능(MemAvailable)을 뺀 값이라 캐시는 쓴 것으로 세지 않는다."""
    raw = _read(path)
    if not raw:
        return None
    kb: dict[str, int] = {}
    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        fields = rest.split()
        if fields and fields[0].isdigit():
            kb[key] = int(fields[0])
    if "MemTotal" not in kb or "MemAvailable" not in kb:
        return None
    total = kb["MemTotal"] * 1024 / GIB
    return round(total - kb["MemAvailable"] * 1024 / GIB, 1), round(total, 1)


def uptime_s(path: Path = UPTIME) -> int | None:
    raw = _read(path)
    try:
        return int(float(raw.split()[0]))  # type: ignore[union-attr]
    except (AttributeError, IndexError, ValueError):
        return None


def disk_free_pct(path: Path = Path("/")) -> float | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return round(usage.free / usage.total * 100, 1)


def collect(now: datetime | None = None, *, thermal: Path = THERMAL, meminfo: Path = MEMINFO,
            uptime: Path = UPTIME, disk: Path = Path("/")) -> dict:
    status: dict = {"updated": (now or datetime.now(KST)).isoformat(timespec="seconds")}
    temp = cpu_temp_c(thermal)
    if temp is not None:
        status["cpu_temp_c"] = temp
    mem = memory_gb(meminfo)
    if mem:
        status["mem_used_gb"], status["mem_total_gb"] = mem
    up = uptime_s(uptime)
    if up is not None:
        status["uptime_s"] = up
    free = disk_free_pct(disk)
    if free is not None:
        status["disk_free_pct"] = free
    return status


def write(path: Path, status: dict) -> None:
    # Caddy와 브라우저가 읽는 공개 파일이라 누구나 읽을 수 있게 한다
    write_atomic(path, json.dumps(status, ensure_ascii=False, indent=2) + "\n", mode=0o644)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="status", description="Pi 상태를 status.json에 한 번 쓴다")
    parser.add_argument("--out", type=Path, help=f"쓸 위치 (기본: HUNINN_STATUS_PATH, 없으면 {DEFAULT_PATH})")
    parser.add_argument("--print", action="store_true", dest="show", help="파일에 쓰지 않고 내용만 보여 준다")
    args = parser.parse_args(argv)
    status = collect()
    if args.show:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    path = args.out or Path(os.environ.get("HUNINN_STATUS_PATH") or DEFAULT_PATH)
    try:
        write(path, status)
    except OSError as e:
        print(f"status.json을 쓰지 못했다: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
