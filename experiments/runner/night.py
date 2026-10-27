#!/usr/bin/env python3
"""밤 실행: 계획(plan)의 작업을 시간대 안에서 차례로 돈다 (docs/experiments.md 7절).

    python3 experiments/runner/night.py --plan experiments/plans/round1-bench.toml --until 05:30

- systemd 유닛 안에서 MemoryMax가 걸려 있을 때만 돈다 (CLAUDE.md: 실험은 systemd 서비스 + MemoryMax로만)
- 실험은 한 번에 하나만 돈다. logs/exp-run.lock을 잡지 못하면 바로 끝낸다
- 실행 중 VS Code 원격 서버가 뜨면 러너가 작업을 멈추고, 여기서 조건이 다시 맞을 때까지 기다렸다가 그 작업을 처음부터 돈다
- 작업마다 시작 조건(7.2절: VS Code 서버, Huninn 사이클, MemAvailable, 부하)을 보고, 안 맞으면 10분 뒤 다시 본다
- 끝낸 작업은 logs/exp-plans/<계획 이름>.json(비공개)에 남기고, 다음 밤에는 남은 작업부터 돈다.
  작업 내용이 바뀌면 키가 달라져 다시 돈다. 실패한 작업은 두 밤까지 다시 시도한다
- --until 시각이 지나면 새 작업을 시작하지 않는다. 도는 작업은 끝까지 간다(유닛의 RuntimeMaxSec가 마지막 장치)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

from common import LOGS_DIR, REPO, acquire_lock, cgroup_value, log_event, now, own_cgroup, start_problems
import llm_bench
import llm_tasks

TEMPLATES = {"llm-bench": llm_bench.run_job, "llm-tasks": llm_tasks.run_job}
FAILS_MAX = 2


def deadline_for(until: str, start: datetime) -> datetime:
    """start 다음에 오는 until(HH:MM) 시각."""
    hour, minute = (int(x) for x in until.split(":"))
    target = start.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > start else target + timedelta(days=1)


def job_key(index: int, job: dict) -> str:
    body = json.dumps(job, sort_keys=True, ensure_ascii=False)
    return f"{index:02d}-{hashlib.sha256(body.encode()).hexdigest()[:8]}"


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def pending(jobs: list[dict], state: dict) -> list[tuple[str, dict]]:
    out = []
    for i, job in enumerate(jobs):
        key = job_key(i, job)
        entry = state.get(key, {})
        if entry.get("status") == "done" or entry.get("fails", 0) >= FAILS_MAX:
            continue
        out.append((key, job))
    return out


def wait_for_start(deadline: datetime, recheck_s: int) -> bool:
    """시작 조건이 맞으면 True. 시간대 안에서 recheck_s마다 다시 보고, 시간대가 끝나면 False."""
    while True:
        problems = start_problems(cgroup_value(own_cgroup(), "memory.max"))
        if not problems:
            return True
        if now() + timedelta(seconds=recheck_s) >= deadline:
            log_event("night-postponed", problems=problems, reason="시간대 안에 시작 조건이 맞지 않았다")
            return False
        log_event("night-wait", problems=problems, recheck_s=recheck_s)
        time.sleep(recheck_s)


def run_plan(plan_path: Path, deadline: datetime, recheck_s: int) -> int:
    with plan_path.open("rb") as f:
        plan = tomllib.load(f)
    name = plan.get("name") or plan_path.stem
    jobs = plan.get("job", [])
    state_path = LOGS_DIR / "exp-plans" / f"{name}.json"
    state = load_state(state_path)
    todo = pending(jobs, state)
    log_event("night-start", plan=name, jobs=len(jobs), pending=len(todo), until=deadline.isoformat(timespec="minutes"))
    if not todo:
        log_event("night-end", plan=name, reason="계획의 작업을 모두 끝냈다")
        return 0

    for key, job in todo:
        run = TEMPLATES.get(job.get("template"))
        entry = state.setdefault(key, {"job": job, "fails": 0})
        if run is None:
            entry.update(status="failed", fails=FAILS_MAX, error=f"모르는 템플릿 {job.get('template')}")
            save_state(state_path, state)
            continue
        while True:  # VS Code 연결로 멈춘 작업은 조건이 다시 맞으면 처음부터 돈다
            if now() >= deadline:
                log_event("night-end", plan=name, reason="시간대가 끝났다", left=len(pending(jobs, state)))
                return 0
            if not wait_for_start(deadline, recheck_s):
                return 0
            try:
                summary = run({k: v for k, v in job.items() if k != "template"})
            except Exception as e:  # 작업 하나의 실패로 밤 전체를 멈추지 않는다
                entry["fails"] = entry.get("fails", 0) + 1
                entry.update(status="failed", error=f"{type(e).__name__}: {e}", at=now().isoformat(timespec="seconds"))
                log_event("night-job-failed", plan=name, key=key, error=entry["error"])
                save_state(state_path, state)
                break
            if summary.get("aborted"):
                entry.setdefault("aborted_runs", []).append(summary["run_id"])
                log_event("night-job-aborted", plan=name, key=key, reason=summary["aborted"], run_id=summary["run_id"])
                save_state(state_path, state)
                continue
            entry.update(status="done", run_id=summary["run_id"], result=summary.get("headline"),
                         at=now().isoformat(timespec="seconds"))
            save_state(state_path, state)
            break

    left = len(pending(jobs, state))
    log_event("night-end", plan=name, reason="남은 작업 없음" if not left else "실패한 작업이 남았다", left=left)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="계획의 실험 작업을 시간대 안에서 차례로 돈다")
    parser.add_argument("--plan", required=True, type=Path, action="append",
                        help="계획 파일. 여러 번 주면 차례로 돈다")
    parser.add_argument("--until", default="05:30", help="새 작업을 시작하지 않는 시각 (HH:MM, KST)")
    parser.add_argument("--recheck-min", type=int, default=10, help="시작 조건이 안 맞을 때 다시 보는 간격(분)")
    args = parser.parse_args()
    if cgroup_value(own_cgroup(), "memory.max") is None:
        print("메모리 상한 없이 실행할 수 없다 (CLAUDE.md: 실험은 systemd 서비스 + MemoryMax로만)", file=sys.stderr)
        return 2
    lock = acquire_lock()
    if lock is None:
        print("다른 실험이 돌고 있다 (logs/exp-run.lock)", file=sys.stderr)
        return 3
    deadline = deadline_for(args.until, now())  # 계획이 여럿이어도 마감은 하나다
    for plan in args.plan:
        if now() >= deadline:
            log_event("night-end", plan=plan.stem, reason="시간대가 끝났다")
            break
        run_plan(plan if plan.is_absolute() else REPO / plan, deadline, args.recheck_min * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
