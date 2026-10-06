"""운영 기록 (logs/YYYY-MM-DD.jsonl). logs/는 공개하지 않는다(.gitignore)."""
from __future__ import annotations

import json

from .config import Config


def append(config: Config, event: str, actor: str, **data) -> None:
    now = config.now()
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    record = {"ts": now.isoformat(timespec="seconds"), "actor": actor, "event": event, **data}
    with open(config.logs_dir / f"{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
