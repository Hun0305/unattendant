"""blogops MCP 서버 (stdio). Huninn이 쓸 수 있는 툴은 여기 있는 18개뿐이다 (docs/blogops.md 2절).

실행: python -m blogops.server   (ops/huninn/run-cycle.sh가 mcp.json으로 띄운다)
툴은 다른 모듈을 부르기만 한다. 조건 검사는 각 모듈이 한다.
"""
from __future__ import annotations

import functools
import inspect
import os
import time
from typing import Optional, TypedDict

from mcp.server.mcpserver import MCPServer

from . import backlog, health, indexnow, log, notify, publish, quality, records, summary
from .backlog import BacklogError
from .config import Config
from .env import EnvError
from .indexnow import IndexNowError
from .notify import NotifyError
from .publish import PublishError
from .records import RecordError
from .store import Store, StoreError

INSTRUCTIONS = "unattendant.dev 운영 툴. 시스템은 이 툴로만 건드린다. 툴이 돌려준 결과만 사실로 믿는다."
EXPECTED = (StoreError, RecordError, PublishError, NotifyError, BacklogError, IndexNowError, EnvError,
            ValueError, log.ToolLimitError)

server = MCPServer("blogops", instructions=INSTRUCTIONS)
_ctx: dict = {}


class Source(TypedDict):
    title: str
    url: str


def context() -> tuple[Config, Store, log.CycleGuard]:
    if not _ctx:
        config = Config.from_env()
        _ctx.update(config=config, store=Store(config), guard=log.CycleGuard(config))
    return _ctx["config"], _ctx["store"], _ctx["guard"]


def reset() -> None:
    """테스트용: 환경변수를 바꾼 뒤 설정을 다시 읽는다."""
    _ctx.clear()


def _summarize(kwargs: dict) -> dict:
    # 기록에는 긴 본문 대신 길이만 남긴다
    return {k: (f"<{len(v)}자>" if isinstance(v, str) and len(v) > 200 else v) for k, v in kwargs.items()}


def tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        config, store, guard = context()
        start = time.monotonic()
        try:
            guard.check(fn.__name__)
            result = fn(*args, **kwargs)
            if isinstance(result, dict):
                result.setdefault("ok", True)
            ok = True
        except EXPECTED as e:
            result, ok = {"ok": False, "error": str(e)}, False
        except Exception as e:  # 예상하지 못한 오류도 사이클을 죽이지 않고 알린다
            result, ok = {"ok": False, "error": f"예상하지 못한 오류: {type(e).__name__}: {e}"}, False
        guard.record(fn.__name__, ok, int((time.monotonic() - start) * 1000), args=_summarize(kwargs))
        return result

    server.add_tool(wrapper, name=fn.__name__, description=inspect.getdoc(fn))
    return wrapper


# ── 관측·기획 ────────────────────────────────────────────

@tool
def get_system_health() -> dict:
    """서버 상태: 디스크 여유, CPU 온도, 업타임, 메모리, 사이트 응답, 마지막 빌드, 초안 상태별 수.
    problems가 비어 있지 않으면 notify_human으로 알린다."""
    config, store, _ = context()
    return health.check(config, store)


@tool
def get_strategy() -> dict:
    """운영 전략 문서(state/strategy.md) 전문. 글감을 고르기 전에 읽고 그대로 따른다."""
    config, _, _ = context()
    return {"text": (config.state_dir / "strategy.md").read_text(encoding="utf-8")}


@tool
def get_backlog(status: Optional[str] = None) -> dict:
    """글감 백로그. status로 거를 수 있다: idea(쓸 수 있음), blocked, drafting, published, dropped."""
    config, _, _ = context()
    return {"items": backlog.items(config, status)}


@tool
def manage_backlog(action: str, item_id: str, title: str = "", series: str = "", notes: str = "",
                   sources: Optional[list[str]] = None, status: str = "", note: str = "") -> dict:
    """글감 추가 또는 상태 변경.
    action="add": item_id(영문 소문자·하이픈), title, series(ops-log 등), notes, sources(재료 문서 경로)
    action="set_status": item_id, status(idea·blocked·drafting·published·dropped), note(blocked·dropped는 이유 필수)"""
    config, _, _ = context()
    if action == "add":
        return {"item": backlog.add_item(config, item_id=item_id, title=title, series=series, notes=notes,
                                         sources=sources)}
    if action == "set_status":
        return {"item": backlog.set_status(config, item_id, status, note or None)}
    raise ValueError("action은 add 또는 set_status다")


@tool
def list_posts(series: Optional[str] = None) -> dict:
    """발행된 글 목록(슬러그, 언어, 제목, 날짜, 시리즈, 작성자). series로 거를 수 있다."""
    config, _, _ = context()
    posts = records.site_posts(config)
    return {"posts": [p for p in posts if series is None or series in p["series"]]}


@tool
def search_posts(query: str) -> dict:
    """발행된 글에서 검색어(공백으로 여러 개)가 들어간 글을 찾는다. 새 글이 기존 글과 겹치는지 볼 때 쓴다."""
    config, _, _ = context()
    return {"results": records.search_posts(config, query)}


@tool
def read_record(path: str = "", offset: int = 0) -> dict:
    """공개 기록(docs/*.md, ops/README.md, site/README.md)을 읽는다. path를 비우면 목록을 준다.
    길면 나눠서 준다: next_offset이 있으면 offset에 넣어 이어 읽는다."""
    config, _, _ = context()
    if not path:
        return {"records": records.list_records(config)}
    return records.read_record(config, path, offset)


@tool
def get_git_log(repo: str = "ops", since: Optional[str] = None, limit: int = 30) -> dict:
    """커밋 메시지(제목과 본문, 변경 내용 제외). repo는 ops(운영 레포) 또는 site(사이트 레포),
    since는 YYYY-MM-DD, limit은 최대 100."""
    config, _, _ = context()
    return {"commits": records.git_log(config, repo, since, limit)}


# ── 초안 ─────────────────────────────────────────────────

def _lang(title: str, description: str, tags: Optional[list[str]], body: str) -> Optional[dict]:
    if not (title or description or body):
        return None
    return {"title": title, "description": description, "tags": tags or [], "body": body}


@tool
def create_draft(slug: str, series: str, title: str, description: str, tags: list[str], body: str,
                 sources: Optional[list[Source]] = None, backlog_id: Optional[str] = None,
                 en_title: str = "", en_description: str = "", en_tags: Optional[list[str]] = None,
                 en_body: str = "") -> dict:
    """새 초안. slug는 영문 소문자·하이픈(주소가 된다), series는 ops-log 또는 weekly-report,
    body는 마크다운 본문(# 제목 없이, 소제목은 ##부터). 숫자를 쓰면 sources에 출처를 단다.
    영어판이 필요하면(주간 보고서는 필수) en_*를 채운다. front matter와 date는 넣지 않는다."""
    config, store, _ = context()
    draft_id = store.create_draft(slug=slug, series=series, ko=_lang(title, description, tags, body),
                                  en=_lang(en_title, en_description, en_tags, en_body),
                                  sources=list(sources) if sources else None, backlog_id=backlog_id)
    warnings = []
    if backlog_id:
        try:
            backlog.set_status(config, backlog_id, "drafting")
        except BacklogError as e:
            warnings.append(str(e))
    return {"draft_id": draft_id, "status": store.status(draft_id), "warnings": warnings}


@tool
def update_draft(draft_id: str, note: str, title: str = "", description: str = "",
                 tags: Optional[list[str]] = None, body: str = "", sources: Optional[list[Source]] = None,
                 en_title: str = "", en_description: str = "", en_tags: Optional[list[str]] = None,
                 en_body: str = "") -> dict:
    """초안을 고친다. 바꿀 항목만 채우고, note에 무엇을 왜 고쳤는지 쓴다(반려 사유를 반영했다면 그 내용).
    고치면 품질 검사와 승인 기록은 무효가 되므로 check_quality부터 다시 한다."""
    _, store, _ = context()

    def part(t, d, tg, b):
        changed = {k: v for k, v in (("title", t), ("description", d), ("body", b)) if v}
        if tg:
            changed["tags"] = tg
        return changed or None
    store.update_draft(draft_id, note=note, ko=part(title, description, tags, body),
                       en=part(en_title, en_description, en_tags, en_body),
                       sources=list(sources) if sources else None)
    return {"draft_id": draft_id, "status": store.status(draft_id)}


@tool
def list_drafts() -> dict:
    """초안 목록과 상태: writing(작성 중), ready(품질 통과), awaiting_approval(승인 대기),
    approved(승인됨, 발행 가능), rejected(반려됨, 사유를 보고 고친다), held(보류), published(발행됨)."""
    _, store, _ = context()
    return {"drafts": [{k: d[k] for k in ("draft_id", "status", "title", "series", "backlog_id", "updated_at")}
                       for d in store.list_drafts()]}


@tool
def check_quality(draft_id: str) -> dict:
    """품질 검사. 통과하면 승인을 요청할 수 있다. 실패하면 problems를 보고 update_draft로 고친다.
    서로 다른 버전으로 3번 연달아 실패하면 초안이 보류되고 운영자에게 알림이 간다."""
    config, store, _ = context()
    result = quality.check_quality(config, store, draft_id)
    if result["held"]:
        notify.notify_human(config, "warn", f"초안 `{draft_id}`이 품질 검사를 3번 통과하지 못해 보류됐다. "
                                            f"첫 문제: {result['problems'][0]}")
    return result


@tool
def request_approval(draft_id: str) -> dict:
    """품질 검사를 통과한 초안의 승인을 요청한다. 디스코드 #승인으로 운영자에게 간다.
    승인을 기다리는 초안은 한 번에 하나뿐이다."""
    config, store, _ = context()
    return notify.request_approval(config, store, draft_id)


@tool
def get_approval_status(draft_id: str) -> dict:
    """초안의 승인 상태와 운영자 결정 기록(반려 사유 포함)."""
    _, store, _ = context()
    s = store.summary(draft_id)
    return {"draft_id": draft_id, "status": s["status"], "decisions": store.decisions(draft_id),
            "last_rejection": s["last_rejection"]}


# ── 발행·보고 ────────────────────────────────────────────

@tool
def publish_post(draft_id: str) -> dict:
    """승인된 초안을 발행한다(하루 1편). 사이트에 올리고 커밋·push한 뒤 공개 주소를 확인한다.
    warnings가 있으면 운영자에게도 알림이 간다."""
    config, store, _ = context()
    if os.environ.get("BLOGOPS_NO_PUBLISH"):
        raise PublishError("이번 실행에서는 발행하지 않는다 (BLOGOPS_NO_PUBLISH, 시험 실행)")
    result = publish.publish_post(config, store, draft_id)
    if result["warnings"]:
        notify.notify_human(config, "warn", f"발행은 됐지만 확인할 것이 있다: {result['url']}\n- "
                            + "\n- ".join(result["warnings"]))
    return result


@tool
def request_indexing(urls: list[str]) -> dict:
    """발행한 글 주소의 색인을 검색엔진(IndexNow)에 요청한다. 키 파일이 없으면 건너뛴다."""
    config, _, _ = context()
    if not indexnow.find_key(config):
        return {"skipped": True, "reason": "IndexNow 키 파일이 아직 없다(운영자가 뒤로 미룸). 건너뛰어도 된다"}
    return indexnow.request_indexing(config, urls)


@tool
def get_week_summary(week_start: Optional[str] = None) -> dict:
    """주간 보고서 재료: 그 주(월~일)의 발행, 승인·반려와 사유, 품질 검사 첫 통과율, 보류, 사이클 수와
    비용 추정. week_start(YYYY-MM-DD)를 비우면 이번 주."""
    config, store, _ = context()
    return summary.week(config, store, week_start)


@tool
def notify_human(level: str, message: str) -> dict:
    """운영자에게 디스코드로 알린다. level: info(#일일요약, 하루 요약), warn(#긴급), critical(#긴급, 멘션)."""
    config, _, _ = context()
    return notify.notify_human(config, level, message)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
