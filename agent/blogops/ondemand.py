"""반려·접기 직후 사이클을 바로 한 번 더 돌리기 (docs/blogops.md 12절).

운영자가 반려하거나 접으면 다음 14:00까지 기다리지 않고 Huninn이 바로 다시 쓰게 한다.
    반려  같은 초안을 사유대로 고쳐 다시 승인을 요청한다 (프롬프트 3번)
    접기  다른 글감으로 새 초안을 쓴다 (프롬프트 4번)
승인은 여기에 해당하지 않는다. 승인한 글은 다음 14:00 사이클이 발행한다.

- 이 모듈은 요청 파일(logs/.cycle-request) 하나만 만든다. 사이클은 systemd path 유닛(huninn-cycle-now.path)이
  그 파일을 보고 huninn-cycle.service를 시작한다. 봇과 review 명령에는 서비스를 시작할 권한을 주지 않는다
- 서비스는 시작할 때 요청 파일을 지운다(ExecStartPre). 도는 중에 새 요청이 오면 끝난 뒤 한 번 더 돈다
  (2026-10-13 사용자 매니저의 임시 유닛으로 확인: 1번 요청=1번 실행, 실행 중 요청=끝난 뒤 1번 더, 연속 3번 요청=1번)
- path 유닛이 이 파일을 실제로 지켜볼 때만 요청한다. 아니면 'unwatched'로 돌려주고 다음 14:00 사이클로 안내한다.
  유닛을 설치하기 전이나 작업실에서 시험할 때 거짓말을 하지 않으려는 것이다
- 하루 상한이 있다(config.ondemand_daily_limit, 5회). 반려 → 재작성 → 반려가 되풀이되며 구독 한도를 쓰는 일을 막는다.
  상한을 넘으면 'capped'로 돌려주고 다음 14:00 사이클이 처리한다
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Callable, Optional

from . import log
from .config import Config
from .fileio import write_atomic

PATH_UNIT = "huninn-cycle-now.path"
Runner = Callable[..., subprocess.CompletedProcess]


def watcher_active(config: Config, run: Optional[Runner] = None) -> bool:
    """systemd path 유닛이 켜져 있고, 지켜보는 파일이 이 설정의 요청 파일과 같은가."""
    try:
        result = (run or subprocess.run)(["systemctl", "show", PATH_UNIT, "-p", "ActiveState", "-p", "Paths"],
                                         capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    state, watched = None, []
    for line in (result.stdout or "").splitlines():
        key, _, value = line.partition("=")
        if key == "ActiveState":
            state = value.strip()
        elif key == "Paths":  # 예: /home/hun/unattendant-live/logs/.cycle-request (PathExists)
            watched.append(os.path.realpath(re.sub(r"\s*\(\w+\)\s*$", "", value.strip())))
    return state == "active" and os.path.realpath(config.cycle_request_path) in watched


def count_today(config: Config) -> int:
    """오늘(KST) 받아들인 요청 수."""
    path = config.logs_dir / f"{config.now():%Y-%m-%d}.jsonl"
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        count += record.get("event") == "cycle_requested" and record.get("granted") is True
    return count


def request(config: Config, kind: str, draft_id: str) -> dict:
    """사이클을 바로 돌려 달라고 요청한다. status는 requested · capped · unwatched 중 하나.
    count는 오늘 받아들인 요청 수(이번 것 포함), limit은 하루 상한."""
    limit = config.ondemand_daily_limit
    count = count_today(config)
    base = {"count": count, "limit": limit}
    if not watcher_active(config):
        log.append(config, "cycle_requested", "operator", granted=False, reason="unwatched", kind=kind, draft_id=draft_id)
        return {"status": "unwatched", **base}
    if count >= limit:
        log.append(config, "cycle_requested", "operator", granted=False, reason="capped", kind=kind, draft_id=draft_id)
        return {"status": "capped", **base}
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(config.cycle_request_path, json.dumps(
        {"at": config.now().isoformat(timespec="seconds"), "kind": kind, "draft_id": draft_id}, ensure_ascii=False) + "\n")
    log.append(config, "cycle_requested", "operator", granted=True, kind=kind, draft_id=draft_id, n=count + 1, limit=limit)
    return {"status": "requested", "count": count + 1, "limit": limit}
