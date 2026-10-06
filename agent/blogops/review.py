"""사람용 승인·반려 명령 (docs/blogops.md 4절). Huninn의 툴이 아니다.

    review list [--all]           승인 대기·반려·보류 초안 (--all이면 전부)
    review show <초안ID> [--body]  요약, 품질 검사 결과, 파일 경로
    review approve <초안ID>        지금 내용의 해시로 승인을 기록한다
    review reject <초안ID> "사유"  반려를 기록한다. 사유는 필수
"""
from __future__ import annotations

import argparse
import sys

from . import log
from .config import Config
from .store import STATUS_LABELS, Store, StoreError


def _cmd_list(store: Store, args) -> None:
    drafts = store.list_drafts()
    if not args.all:
        drafts = [d for d in drafts if d["status"] != "published"]
    if not drafts:
        print("초안이 없다." if args.all else "처리할 초안이 없다. (--all로 발행된 초안까지 볼 수 있다)")
        return
    for d in drafts:
        print(f"{d['draft_id']:<36} {STATUS_LABELS[d['status']]:<8} {d['title'] or '(제목 없음)'}")


def _cmd_show(store: Store, args) -> None:
    s = store.summary(args.draft_id)
    print(f"초안    {s['draft_id']}")
    print(f"상태    {STATUS_LABELS[s['status']]}")
    print(f"제목    {s['title']}")
    print(f"요약    {s['description']}")
    print(f"시리즈  {s['series']}   백로그 {s['backlog_id'] or '-'}   언어 {', '.join(s['langs'])}")
    print(f"해시    {s['hash'][:12]}")
    q = s["last_quality"]
    if q:
        result = "통과" if q["passed"] else "실패"
        print(f"품질    {result} ({q['at']})" + "".join(f"\n        - {p}" for p in q["problems"]))
    if s["last_rejection"]:
        r = s["last_rejection"]
        print(f"지난 반려 {r['at']}: {r['reason']}")
    if s["held"]:
        print(f"보류    {s['held']['reason']}")
    for lang, path in store.draft_paths(args.draft_id).items():
        print(f"파일    {path}")
    if args.body:
        _, body = store.fields(args.draft_id, "ko")
        print("\n" + body)


def _cmd_approve(store: Store, args) -> None:
    record = store.record_decision(args.draft_id, "approved")
    log.append(store.config, "approval_decision", "operator",
               draft_id=args.draft_id, decision="approved", hash=record["hash"])
    print(f"승인했다: {args.draft_id} (해시 {record['hash'][:12]})")
    print("다음 사이클(매일 14:00)에서 발행된다. 그 전에 내용이 바뀌면 승인은 풀린다.")


def _cmd_reject(store: Store, args) -> None:
    record = store.record_decision(args.draft_id, "rejected", reason=args.reason)
    log.append(store.config, "approval_decision", "operator",
               draft_id=args.draft_id, decision="rejected", hash=record["hash"], reason=record["reason"])
    print(f"반려했다: {args.draft_id}")
    print("다음 사이클에서 Huninn이 사유를 읽고 고친 뒤, 품질 검사를 거쳐 다시 승인을 요청한다.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="review", description="Huninn 초안 승인·반려")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="처리할 초안 목록")
    p.add_argument("--all", action="store_true", help="발행된 초안까지")
    p = sub.add_parser("show", help="초안 요약")
    p.add_argument("draft_id")
    p.add_argument("--body", action="store_true", help="한국어 본문까지 출력")
    p = sub.add_parser("approve", help="승인")
    p.add_argument("draft_id")
    p = sub.add_parser("reject", help="반려 (사유 필수)")
    p.add_argument("draft_id")
    p.add_argument("reason")
    args = parser.parse_args(argv)

    store = Store(Config.from_env())
    handler = {"list": _cmd_list, "show": _cmd_show, "approve": _cmd_approve, "reject": _cmd_reject}[args.command]
    try:
        handler(store, args)
    except StoreError as e:
        print(f"review: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
