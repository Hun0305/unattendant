"""운영 기록 (logs/YYYY-MM-DD.jsonl). logs/는 공개하지 않는다(.gitignore)."""
from __future__ import annotations

import json
import os

from .config import Config


def append(config: Config, event: str, actor: str, **data) -> None:
    now = config.now()
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": now.isoformat(timespec="seconds"), "actor": actor, "event": event, **data}
    with open(config.logs_dir / f"{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ToolLimitError(Exception):
    pass


class CycleGuard:
    """사이클 하나(claude -p 한 번 = MCP 서버 프로세스 하나)의 툴 호출을 세고 기록한다.

    claude -p에 턴 수 제한 옵션이 없어서(2.1.289) blogops가 상한을 지킨다.
    """

    def __init__(self, config: Config, cycle_id: str | None = None):
        self.config = config
        self.count = 0
        self.cycle = cycle_id or os.environ.get("BLOGOPS_CYCLE_ID") or f"manual-{config.now():%Y%m%dT%H%M%S}"

    def check(self, tool: str) -> None:
        self.count += 1
        if self.count > self.config.max_tool_calls_per_cycle:
            append(self.config, "tool_limit", "huninn", cycle=self.cycle, tool=tool, count=self.count)
            raise ToolLimitError(f"이번 사이클의 툴 호출 상한({self.config.max_tool_calls_per_cycle}회)을 넘었다. 사이클을 끝낸다")

    def record(self, tool: str, ok: bool, ms: int, **summary) -> None:
        append(self.config, "tool_call", "huninn", cycle=self.cycle, n=self.count, tool=tool, ok=ok, ms=ms, **summary)
