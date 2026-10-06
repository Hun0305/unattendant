"""주간 보고서 재료 (get_week_summary). 공개해도 되는 집계만 돌려준다."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Optional

from .config import Config
from .store import Store


def week_bounds(config: Config, week_start: Optional[str]) -> tuple[date, date]:
    start = date.fromisoformat(week_start) if week_start else config.now().date()
    start -= timedelta(days=start.weekday())  # 그 주 월요일
    return start, start + timedelta(days=7)


def _in(ts: str, start: date, end: date) -> bool:
    return start <= datetime.fromisoformat(ts).date() < end


def week(config: Config, store: Store, week_start: Optional[str] = None) -> dict:
    start, end = week_bounds(config, week_start)
    published, decisions, first_pass, quality_runs, held = [], [], [], 0, []
    for d in store.list_drafts():
        meta = store.meta(d["draft_id"])
        if meta.get("published") and _in(meta["published"]["at"], start, end):
            published.append({"title": d["title"], "url": meta["published"]["url"], "at": meta["published"]["at"]})
        for dec in store.decisions(d["draft_id"]):
            if _in(dec["at"], start, end):
                decisions.append({"draft": d["title"], "decision": dec["decision"], "at": dec["at"],
                                  **({"reason": dec["reason"]} if dec.get("reason") else {})})
        quality = [q for q in meta.get("quality", []) if _in(q["at"], start, end)]
        quality_runs += len(quality)
        if meta.get("quality") and _in(meta["quality"][0]["at"], start, end):
            first_pass.append(meta["quality"][0]["passed"])
        if meta.get("held") and _in(meta["held"]["at"], start, end):
            held.append({"draft": d["title"], "reason": meta["held"]["reason"]})

    cycles = []
    cycles_file = config.logs_dir / "cycles.jsonl"
    if cycles_file.exists():
        for line in cycles_file.read_text(encoding="utf-8").splitlines():
            c = json.loads(line)
            if _in(c["ts"], start, end):
                cycles.append(c)
    return {
        "week": f"{start.isoformat()} ~ {(end - timedelta(days=1)).isoformat()}",
        "published": published,
        "approval_decisions": decisions,
        "quality": {"runs": quality_runs, "new_drafts": len(first_pass), "first_pass": sum(first_pass),
                    "first_pass_rate": round(sum(first_pass) / len(first_pass), 2) if first_pass else None},
        "held": held,
        "cycles": {"count": len(cycles), "failed": sum(1 for c in cycles if c.get("is_error")),
                   "cost_usd_estimate": round(sum(c.get("total_cost_usd") or 0 for c in cycles), 4),
                   "note": "Phase 1은 Pro 구독이라 비용은 claude -p가 계산한 추정치다 (실제 청구 아님)"},
    }
