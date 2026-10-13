"""운영자의 결정: 승인, 반려, 접기 (docs/blogops.md 4·11절). review 명령과 디스코드 봇이 같이 쓴다.

기록(store)과 로그는 여기서 한 번만 남기고, 어디서 결정했는지는 via(cli·discord)로 구분한다.
결정 뒤 정리(#승인 메시지의 버튼 걷어내기, 미리보기 삭제)는 finish()가 따로 한다.
디스코드는 버튼에 3초 안에 응답해야 해서, 봇은 응답한 다음에 finish()를 부른다.

접기(drop) = 반려 + 보류 + 글감 blocked. 사유가 "고쳐라"가 아니라 "이 주제는 그만"일 때 쓴다.
반려만 하면 Huninn이 다음 사이클에 같은 글을 다시 고치려 한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import backlog, env, log, notify, preview
from .config import Config
from .httpjson import Transport
from .store import STATUS_LABELS, Store, StoreError

KINDS = ("approved", "rejected", "dropped")
HEADS = {"approved": "✅ **승인함**", "rejected": "❌ **반려함**", "dropped": "🗂 **접음**"}
NEXT_STEP = {
    "approved": "다음 사이클(매일 14:00)에서 발행된다. 그 전에 내용이 바뀌면 승인은 풀린다.",
    "rejected": "다음 사이클에서 Huninn이 사유를 읽고 고친 뒤, 품질 검사를 거쳐 다시 승인을 요청한다.",
    "dropped": "이 글은 더 고치지 않는다. 글감은 blocked로 바꿨다.",
}


@dataclass(frozen=True)
class Decision:
    draft_id: str
    kind: str  # approved | rejected | dropped
    hash: str
    at: str
    via: str
    reason: Optional[str] = None
    warnings: tuple[str, ...] = ()  # 결정은 났지만 곁다리 처리(글감 상태 등)가 안 된 것


def preflight(store: Store, draft_id: str, hash12: str) -> dict:
    """버튼을 눌렀을 때 먼저 본다. 사람이 본 그 버전이 아직 승인 대기가 아니면 StoreError (메시지는 그대로 보여 준다)."""
    summary = store.summary(draft_id)
    if not summary["hash"].startswith(hash12):
        raise StoreError("본 뒤에 초안이 바뀌었다. 최신 승인 요청 메시지에서 다시 확인해라")
    if summary["status"] != "awaiting_approval":
        raise StoreError(f"이미 처리됐거나 승인 대기가 아니다 (지금: {STATUS_LABELS[summary['status']]})")
    return summary


def approve(config: Config, store: Store, draft_id: str, *, expect_hash: Optional[str] = None,
            via: str = "cli") -> Decision:
    record = store.record_decision(draft_id, "approved", via=via, expect_hash=expect_hash)
    log.append(config, "approval_decision", "operator",
               draft_id=draft_id, decision="approved", hash=record["hash"], via=via)
    return Decision(draft_id, "approved", record["hash"], record["at"], via)


def reject(config: Config, store: Store, draft_id: str, reason: str, *, drop: bool = False,
           expect_hash: Optional[str] = None, via: str = "cli") -> Decision:
    record = store.record_decision(draft_id, "rejected", reason=reason, via=via, expect_hash=expect_hash)
    reason = record["reason"]
    warnings: list[str] = []
    if drop:
        store.mark_held(draft_id, f"운영자가 접었다: {reason}")
        backlog_id = store.meta(draft_id).get("backlog_id")
        if not backlog_id:
            warnings.append("초안에 글감 ID가 없어 백로그는 그대로다")
        else:
            try:
                backlog.set_status(config, backlog_id, "blocked", note=f"접음({draft_id}): {reason}")
            except backlog.BacklogError as e:
                warnings.append(f"글감 {backlog_id}를 blocked로 바꾸지 못했다: {e}")
    log.append(config, "approval_decision", "operator", draft_id=draft_id, decision="rejected",
               hash=record["hash"], reason=reason, via=via, dropped=drop)
    return Decision(draft_id, "dropped" if drop else "rejected", record["hash"], record["at"], via,
                    reason=reason, warnings=tuple(warnings))


def result_text(title: str, decision: Decision) -> str:
    """결정이 난 #승인 메시지를 대신할 글. 명령 안내와 버튼은 없앤다."""
    where = "디스코드" if decision.via == "discord" else "Pi 명령"
    lines = [f"{HEADS[decision.kind]} — {title}",
             f"초안 `{decision.draft_id}` · 해시 `{decision.hash[:12]}` · {decision.at[:16].replace('T', ' ')} ({where})"]
    if decision.reason:
        lines.append(f"사유: {decision.reason}")
    lines.append(NEXT_STEP[decision.kind])
    return "\n".join(lines)


def finish(config: Config, store: Store, decision: Decision, transport: Optional[Transport] = None) -> list[str]:
    """결정 뒤 정리. 실패해도 결정은 이미 기록됐으니 경고만 돌려준다."""
    warnings = list(decision.warnings)
    try:
        preview.cleanup(config, store)
    except OSError as e:
        warnings.append(f"미리보기 폴더를 지우지 못했다: {e}")
    try:
        title = store.summary(decision.draft_id)["title"]
        notify.close_approval_message(config, store, decision.draft_id, decision.hash,
                                      result_text(title, decision), transport=transport)
    except (notify.NotifyError, env.EnvError, StoreError, OSError) as e:
        warnings.append(f"디스코드 승인 요청 메시지를 고치지 못했다: {e}")
    return warnings
