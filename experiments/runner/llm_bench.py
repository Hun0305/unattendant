#!/usr/bin/env python3
"""템플릿 llm-bench: llama-bench로 프롬프트 처리·생성 속도를 잰다 (docs/experiments.md 5.1절, 10절).

    systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 \\
        python3 experiments/runner/llm_bench.py --model llama-3.2-1b
    ... --model llama-3.2-1b --threads 1,2,3 --tests pp512,tg128

- 범위와 고정값은 experiments/templates/llm-bench/template.toml에서 읽는다
- 시험(pp512, tg128, tg128@d2048)과 스레드 수마다 llama-bench를 따로 실행하고, 사이사이 CPU가 식기를 기다린다
- 측정 구간에 무효 조건(7.4절)이 있으면 한 번 다시 재고, 또 무효면 사유와 함께 무효로 남긴다
- Huninn 사이클이 시작되면 지금 시험을 멈추고, 사이클이 끝난 뒤 다시 잰다 (7.1절)
- 실행 중 CPU가 80°C에 닿으면 멈추고 다시 재지 않는다 (architecture.md "실험 중 과열" 가드레일)
- 실행 중 VS Code 원격 서버가 뜨면 작업을 멈춘다(aborted). 다시 도는 것은 night.py가 한다
- 결과: experiments/results/llm-bench/<실행 ID>/, 한 줄 요약은 experiments/results/llm-bench/summary.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from pathlib import Path

from common import (EXP_DIR, LLAMA_DIR, RESULTS_DIR, TEMP_ABORT_C, acquire_lock, code_version, cgroup_value, cycle_active,
                    evict_page_cache, llama_info, loadavg1, log_event, meminfo, model_file, now, oom_kills, own_cgroup,
                    system_info, temp_c, throttled, vscode_pids, wait_cool, wait_cycle)
from telemetry import Telemetry, judge

TEMPLATE_PATH = EXP_DIR / "templates" / "llm-bench" / "template.toml"
LLAMA_BENCH = Path(os.environ.get("EXP_LLAMA_BENCH", LLAMA_DIR / "build" / "bin" / "llama-bench"))
CYCLE_INTERRUPTS_MAX = 3
SUMMARY_FIELDS = ["run_id", "date", "model", "quant", "test", "threads", "avg_ts", "stddev_ts", "samples",
                  "peak_rss_mb", "start_temp_c", "max_temp_c", "other_cpu_pct", "valid", "reasons",
                  "llama_cpp", "model_sha256"]


def load_template() -> tuple[dict, str]:
    raw = TEMPLATE_PATH.read_bytes()
    return tomllib.loads(raw.decode()), hashlib.sha256(raw).hexdigest()[:12]


def check_params(template: dict, quant: str, tests: list[str], threads: list[int]) -> None:
    p = template["params"]
    if quant not in p["quants"]:
        raise ValueError(f"양자화 {quant}는 범위 밖이다: {p['quants']}")
    if bad := [t for t in tests if t not in p["tests"]]:
        raise ValueError(f"시험 {bad}는 범위 밖이다: {p['tests']}")
    if bad := [t for t in threads if t not in p["threads"]]:
        raise ValueError(f"스레드 {bad}는 범위 밖이다: {p['threads']}")


def read_cold(path: Path) -> dict:
    """모델 파일을 페이지 캐시에서 비운 뒤 끝까지 읽는다. SD카드에서 읽는 시간(콜드 로드의 디스크 몫)을 재고,
    이후 측정은 RAM에서 읽게 한다. 첫 측정에 디스크 I/O의 커널 CPU가 섞여 무효가 나는 것을 막는다."""
    evict_page_cache(path)
    fd = os.open(path, os.O_RDONLY)
    try:
        started, total = time.monotonic(), 0
        while chunk := os.read(fd, 8 << 20):
            total += len(chunk)
        seconds = max(time.monotonic() - started, 1e-6)
    finally:
        os.close(fd)
    return {"seconds": round(seconds, 2), "mb_per_s": round(total / seconds / 1e6, 1)}


def run_invocation(cmd: list[str], err_path: Path, timeout_s: int) -> tuple[str, int, float, str | None]:
    """llama-bench를 한 번 실행한다. (표준 출력, 종료 코드, 최대 RSS(MB), 중단 사유)."""
    why: dict[str, str] = {}
    with err_path.open("w") as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True)
        done = threading.Event()

        def watch() -> None:
            deadline = time.monotonic() + timeout_s
            while not done.wait(5):
                t = temp_c()
                if cycle_active():
                    reason = "cycle"
                elif vscode_pids():  # CLAUDE.md: VS Code 원격 연결 중에는 LLM 실험을 돌리지 않는다
                    reason = "vscode"
                elif t is not None and t >= TEMP_ABORT_C:
                    reason = "temp"
                elif time.monotonic() > deadline:
                    reason = "timeout"
                else:
                    reason = None
                if reason:
                    why["interrupted"] = reason
                    proc.send_signal(signal.SIGTERM)
                    if done.wait(15):
                        return
                    proc.kill()
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        out = proc.stdout.read()
        proc.stdout.close()
        _, status, usage = os.wait4(proc.pid, 0)  # 이 자식만의 최대 RSS를 얻으려고 직접 기다린다
        proc.returncode = os.waitstatus_to_exitcode(status)
        done.set()
        watcher.join()
    return out, proc.returncode, round(usage.ru_maxrss / 1024, 1), why.get("interrupted")


def measure(path: Path, test: str, threads: int, attempt: int, spec: dict, template: dict,
            tel: Telemetry, cg: Path, logs: Path) -> dict:
    cycle_wait_s = wait_cycle()
    start_temp, cooldown_s = wait_cool()
    cmd = [str(LLAMA_BENCH), "-m", str(path), "-t", str(threads), "-r", str(spec["reps"]), "-o", "jsonl",
           "--load-mode", template["fixed"]["load_mode"], *spec["args"]]
    ooms = oom_kills(cg)
    t0 = time.time()
    out, code, peak_rss_mb, interrupted = run_invocation(
        cmd, logs / f"{test}-t{threads}-a{attempt}.stderr.txt", template["invocation_timeout_min"] * 60)
    t1 = time.time()
    results = []
    for line in out.splitlines():
        try:
            results.append(json.loads(line))
        except ValueError:
            continue
    valid, reasons, stats = judge(tel.window(t0, t1), start_temp)
    oom = oom_kills(cg) > ooms
    if oom:
        reasons.append("메모리 상한 초과(OOM)")
    if interrupted:
        reasons.append(f"중단: {interrupted}")
    if code != 0 and not oom and not interrupted:
        reasons.append(f"종료 코드 {code}")
    if not results and code == 0:
        reasons.append("llama-bench 결과가 없다")
    return {
        "test": test, "threads": threads, "attempt": attempt, "cmd": cmd[1:],
        "t_start": round(t0, 3), "t_end": round(t1, 3), "seconds": round(t1 - t0, 1),
        "start_temp_c": start_temp, "cooldown_s": cooldown_s, "cycle_wait_s": cycle_wait_s,
        "exit_code": code, "interrupted": interrupted, "oom": oom, "peak_rss_mb": peak_rss_mb,
        "valid": not reasons, "reasons": reasons, "telemetry": stats, "results": results,
    }


def run_job(job: dict) -> dict:
    """작업 하나(모델 하나, 양자화 하나, 시험·스레드 목록)를 재고 결과 폴더를 쓴다. 요약을 돌려준다."""
    template, template_hash = load_template()
    quant = job.get("quant", "Q4_K_M")
    tests = list(job.get("tests", template["params"]["tests"]))
    threads = [int(t) for t in job.get("threads", [4])]
    check_params(template, quant, tests, threads)
    model, entry, path = model_file(job["model"], quant)

    started = now()
    run_id = f"{started:%Y%m%dT%H%M%S}-{model['id']}-{quant}-t{''.join(map(str, threads))}"
    run_dir = RESULTS_DIR / "llm-bench" / run_id
    run_dir.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"exp-{run_id}-", dir="/tmp"))  # 실행 중 기록은 RAM에
    cg = own_cgroup()
    info = llama_info()
    cold = read_cold(path)
    conditions = {
        "run_id": run_id, "template": {"id": template["id"], "version": template["version"], "sha256": template_hash},
        "started": started.isoformat(timespec="seconds"),
        "model": {k: model.get(k) for k in ("id", "name", "maker", "released", "structure", "license", "thinking")},
        "file": entry, "params": {"quant": quant, "tests": tests, "threads": threads,
                                  "reps": {t: template["tests"][t]["reps"] for t in tests},
                                  "load_mode": template["fixed"]["load_mode"]},
        "system": system_info(), "llama_cpp": info, "code": code_version(),
        "model_file_cold_read": cold,
        "start": {"temp_c": temp_c(), "mem_available_mb": meminfo().get("MemAvailable", 0) >> 20,
                  "load1": loadavg1(), "throttled": throttled(), "vscode_processes": len(vscode_pids()),
                  "memory_max_mb": (cgroup_value(cg, "memory.max") or 0) >> 20 or None,
                  "swap_max_mb": None if cgroup_value(cg, "memory.swap.max") is None
                  else cgroup_value(cg, "memory.swap.max") >> 20},
    }
    (run_dir / "conditions.json").write_text(json.dumps(conditions, ensure_ascii=False, indent=2) + "\n")
    log_event("llm-bench-start", run_id=run_id, model=model["id"], quant=quant, tests=tests, threads=threads)

    tel = Telemetry(tmp / "telemetry.csv", cg)
    tel.start()
    records, aborted = [], None
    try:
        for t in threads:
            if aborted:
                break
            for test in tests:
                attempt, cycle_interrupts = 1, 0
                while True:
                    rec = measure(path, test, t, attempt, template["tests"][test], template, tel, cg, tmp)
                    records.append(rec)
                    log_event("llm-bench-test", run_id=run_id, test=test, threads=t, attempt=attempt,
                              valid=rec["valid"], reasons=rec["reasons"], seconds=rec["seconds"],
                              avg_ts=[r.get("avg_ts") for r in rec["results"]])
                    if rec["interrupted"] == "vscode":
                        aborted = "vscode"  # 작업을 멈춘다. night.py가 연결이 끊긴 뒤 처음부터 다시 돈다
                        break
                    if rec["interrupted"] == "cycle" and cycle_interrupts < CYCLE_INTERRUPTS_MAX:
                        cycle_interrupts += 1  # 사이클에 양보한 것은 시도로 세지 않는다
                        continue
                    if rec["valid"] or rec["oom"] or rec["interrupted"] == "temp" or attempt >= template["max_attempts"]:
                        break
                    attempt += 1
                if aborted:
                    break
    finally:
        tel.stop()
        summary = write_outputs(run_dir, tmp, conditions, records, entry, info, aborted)
        shutil.rmtree(tmp, ignore_errors=True)
    log_event("llm-bench-end", run_id=run_id, valid=summary["valid_tests"], total=summary["tests"], aborted=aborted)
    return summary


def write_outputs(run_dir: Path, tmp: Path, conditions: dict, records: list[dict], entry: dict, info: dict,
                  aborted: str | None = None) -> dict:
    with (run_dir / "bench.jsonl").open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if (tmp / "telemetry.csv").exists():
        with (tmp / "telemetry.csv").open("rb") as src, gzip.open(run_dir / "telemetry.csv.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    with gzip.open(run_dir / "stderr.log.gz", "wt") as dst:  # llama-bench가 찍은 모델 정보와 경고
        for log in sorted(tmp.glob("*.stderr.txt")):
            dst.write(f"===== {log.name}\n{log.read_text(errors='replace')}\n")

    final: dict[tuple[str, int], dict] = {}
    for rec in records:  # 시험·스레드마다 마지막 시도가 최종이다
        final[(rec["test"], rec["threads"])] = rec
    rows = []
    for (test, threads), rec in final.items():
        result = rec["results"][0] if rec["results"] else {}
        rows.append({
            "run_id": conditions["run_id"], "date": conditions["started"], "model": conditions["model"]["id"],
            "quant": conditions["params"]["quant"], "test": test, "threads": threads,
            "avg_ts": round(result["avg_ts"], 3) if "avg_ts" in result else None,
            "stddev_ts": round(result["stddev_ts"], 3) if "stddev_ts" in result else None,
            "samples": len(result.get("samples_ts", [])) or None,
            "peak_rss_mb": rec["peak_rss_mb"], "start_temp_c": rec["start_temp_c"],
            "max_temp_c": rec["telemetry"]["max_temp_c"], "other_cpu_pct": rec["telemetry"]["other_cpu_avg_pct"],
            "valid": rec["valid"], "reasons": "; ".join(rec["reasons"]),
            "llama_cpp": f"{info.get('tag') or ''}@{(info.get('commit') or '')[:7]}",
            "model_sha256": entry["sha256"][:12],
        })
    valid = sum(r["valid"] for r in rows)
    summary = {"run_id": conditions["run_id"], "tests": len(rows), "valid_tests": valid,
               "attempts": len(records), "aborted": aborted, "headline": f"유효 {valid}/{len(rows)}", "rows": rows}
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    table = run_dir.parent / "summary.csv"
    new = not table.exists()
    with table.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerows(rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="llama-bench 속도 측정 (템플릿 llm-bench)")
    parser.add_argument("--model", required=True, help="models.toml의 id")
    parser.add_argument("--quant", default="Q4_K_M")
    parser.add_argument("--tests", default="", help="쉼표 목록 (기본: 템플릿의 모든 시험)")
    parser.add_argument("--threads", default="4", help="쉼표 목록 (예: 1,2,3)")
    args = parser.parse_args()
    if cgroup_value(own_cgroup(), "memory.max") is None:
        print("메모리 상한 없이 실행할 수 없다 (CLAUDE.md: 실험은 systemd 서비스 + MemoryMax로만).\n"
              "예: systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 "
              "python3 experiments/runner/llm_bench.py --model llama-3.2-1b", file=sys.stderr)
        return 2
    lock = acquire_lock()
    if lock is None:
        print("다른 실험이 돌고 있다 (logs/exp-run.lock)", file=sys.stderr)
        return 3
    job = {"model": args.model, "quant": args.quant, "threads": [int(t) for t in args.threads.split(",")]}
    if args.tests:
        job["tests"] = args.tests.split(",")
    summary = run_job(job)
    print(json.dumps({k: summary[k] for k in ("run_id", "tests", "valid_tests")}, ensure_ascii=False))
    return 0 if summary["valid_tests"] == summary["tests"] else 1


if __name__ == "__main__":
    sys.exit(main())
