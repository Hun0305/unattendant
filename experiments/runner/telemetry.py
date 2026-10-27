"""공통 로거와 무효 판정 (docs/experiments.md 7.3·7.4절).

실험 동안 1초마다 온도, 클럭, 스로틀링 비트, 메모리, 스왑, CPU를 남긴다. 실행 중에는 /tmp(RAM)에 쓴다.
CPU는 전체 사용률에서 이 실험 cgroup의 몫을 빼 "다른 프로세스 CPU"로 남긴다. 모두 4코어 전체 대비 %다.
"""
from __future__ import annotations

import csv
import os
import threading
import time
from pathlib import Path

from common import (START_TEMP_MAX_C, arm_mhz, cgroup_cpu_usec, cgroup_value, cpu_ticks, meminfo, temp_c,
                    throttled, vmstat)

FIELDS = ["t", "temp_c", "arm_mhz", "throttled", "mem_avail_mb", "cg_mem_mb", "pswpin", "pswpout",
          "pgmajfault", "cpu_total_pct", "cpu_ours_pct", "cpu_other_pct", "power_w"]

OTHER_CPU_MAX_PCT = 5.0  # 다른 프로세스 CPU 평균 상한
SWAP_PAGES_MAX = 256     # 스왑 입출력 합 상한(페이지, 1MB). 그보다 크면 메모리 압박으로 본다
THROTTLE_NOW_MASK = 0xF  # 저전압, 클럭 제한, 스로틀링, 소프트 온도 제한 (지금 상태 비트)


class Telemetry:
    def __init__(self, path: Path, cgroup: Path, interval: float = 1.0):
        self.path, self.cgroup, self.interval = path, cgroup, interval
        self.rows: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="telemetry", daemon=True)
        self._lock = threading.Lock()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def window(self, t0: float, t1: float) -> list[dict]:
        with self._lock:
            return [r for r in self.rows if t0 <= r["t"] <= t1]

    def _run(self) -> None:
        ncpu_us = None
        prev = None
        with self.path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            while not self._stop.is_set():
                t = time.time()
                busy, total = cpu_ticks()
                ours_us = cgroup_cpu_usec(self.cgroup)
                vm = vmstat()
                row = {
                    "t": round(t, 3), "temp_c": temp_c(), "arm_mhz": arm_mhz(), "throttled": throttled(),
                    "mem_avail_mb": meminfo().get("MemAvailable", 0) >> 20,
                    "cg_mem_mb": (cgroup_value(self.cgroup, "memory.current") or 0) >> 20,
                    "pswpin": vm.get("pswpin"), "pswpout": vm.get("pswpout"), "pgmajfault": vm.get("pgmajfault"),
                    "cpu_total_pct": None, "cpu_ours_pct": None, "cpu_other_pct": None, "power_w": None,
                }
                if prev:
                    d_total = total - prev["total"]
                    if d_total > 0:
                        total_pct = (busy - prev["busy"]) / d_total * 100
                        row["cpu_total_pct"] = round(total_pct, 1)
                        if ours_us is not None and prev["ours_us"] is not None:
                            ncpu_us = ncpu_us or (os.cpu_count() or 1) * 1e6
                            ours_pct = (ours_us - prev["ours_us"]) / ((t - prev["t"]) * ncpu_us) * 100
                            row["cpu_ours_pct"] = round(ours_pct, 1)
                            row["cpu_other_pct"] = round(max(0.0, total_pct - ours_pct), 1)
                prev = {"t": t, "busy": busy, "total": total, "ours_us": ours_us}
                writer.writerow(row)
                f.flush()
                with self._lock:
                    self.rows.append(row)
                self._stop.wait(max(0.0, self.interval - (time.time() - t)))


def judge(rows: list[dict], start_temp: float | None) -> tuple[bool, list[str], dict]:
    """측정 구간의 기록으로 유효한지 본다. (유효, 무효 사유, 요약)."""
    temps = [r["temp_c"] for r in rows if r["temp_c"] is not None]
    clocks = [r["arm_mhz"] for r in rows if r["arm_mhz"] is not None]
    others = [r["cpu_other_pct"] for r in rows if r["cpu_other_pct"] is not None]
    flags = 0
    for r in rows:
        flags |= (r["throttled"] or 0) & THROTTLE_NOW_MASK
    swap = majflt = None
    if len(rows) >= 2 and rows[0]["pswpin"] is not None:
        swap = (rows[-1]["pswpin"] - rows[0]["pswpin"]) + (rows[-1]["pswpout"] - rows[0]["pswpout"])
        majflt = rows[-1]["pgmajfault"] - rows[0]["pgmajfault"]
    stats = {
        "samples": len(rows),
        "max_temp_c": max(temps) if temps else None,
        "min_arm_mhz": min(clocks) if clocks else None,
        "throttled_bits": hex(flags),
        "swap_pages": swap,
        "major_faults": majflt,
        "other_cpu_avg_pct": round(sum(others) / len(others), 1) if others else None,
    }
    reasons = []
    if start_temp is not None and start_temp > START_TEMP_MAX_C:
        reasons.append(f"시작 온도 {start_temp}°C > {START_TEMP_MAX_C}°C")
    if flags:
        reasons.append(f"스로틀링·저전압 비트 {hex(flags)}")
    if swap is not None and swap > SWAP_PAGES_MAX:
        reasons.append(f"스왑 입출력 {swap}페이지")
    if stats["other_cpu_avg_pct"] is not None and stats["other_cpu_avg_pct"] > OTHER_CPU_MAX_PCT:
        reasons.append(f"다른 프로세스 CPU 평균 {stats['other_cpu_avg_pct']}%")
    return not reasons, reasons, stats
