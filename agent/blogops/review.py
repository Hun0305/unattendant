"""사람용 승인·반려 명령 (docs/blogops.md 4절). Huninn의 툴이 아니다.

    review list [--all]           승인 대기·반려·보류 초안 (--all이면 전부)
    review show <초안ID> [--body]  요약, 품질 검사 결과, 고친 이력, 파일 경로, 미리보기 주소
    review diff <초안ID> [--en]    지난 반려 판과 지금 판의 차이 (반려가 없으면 첫 판과). Huninn이 무엇을 고쳤는지 본다
    review preview <초안ID>        승인 대기 초안의 미리보기를 (없으면) 만들고 주소를 보인다
    review approve <초안ID>        지금 내용의 해시로 승인을 기록한다
    review reject <초안ID> "사유"  반려를 기록한다. 사유는 필수. --drop이면 글감을 접는다(반려 + 보류 + 글감 blocked)

디스코드 #승인의 버튼은 같은 기록을 남긴다 (blogops/decisions.py, bot.py).
"""
from __future__ import annotations

import argparse
import difflib
import sys

from . import decisions, preview
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
    revisions = store.meta(args.draft_id).get("revisions", [])
    if len(revisions) > 1:
        print("고친 이력" + "".join(f"\n        {r['at']} {r['hash'][:12]} {r['note']}" for r in revisions[1:]))
    if s["status"] == "awaiting_approval":
        found = preview.current(store.config, store, args.draft_id)
        if found:
            for lang, url in found["urls"].items():
                print(f"미리보기 {lang} {url}")
    for lang, path in store.draft_paths(args.draft_id).items():
        print(f"파일    {path}")
    for path in store.asset_paths(args.draft_id):
        print(f"그림    {path.name} ({path.stat().st_size // 1000}KB)")
    if args.body:
        _, body = store.fields(args.draft_id, "ko")
        print("\n" + body)


def _cmd_diff(store: Store, args) -> None:
    lang = "en" if args.en else "ko"
    rejected = [d for d in store.decisions(args.draft_id) if d["decision"] == "rejected"]
    revisions = store.meta(args.draft_id).get("revisions", [])
    base, label = (rejected[-1]["hash"], f"지난 반려 판 ({rejected[-1]['at']})") if rejected \
        else (revisions[0]["hash"], f"첫 판 ({revisions[0]['at']})")
    now = store.content_hash(args.draft_id)
    if base == now:
        print(f"{label}에서 바뀐 것이 없다.")
        return
    old_text, new_text = store.version_text(args.draft_id, base, lang), store.version_text(args.draft_id, now, lang)
    if old_text is None:
        raise StoreError(f"{label}의 {lang}판이 남아 있지 않다 (이전 판 보관은 2026-10-27부터)")
    diff = difflib.unified_diff(old_text.splitlines(), (new_text or "").splitlines(), lineterm="",
                                fromfile=f"{label} {base[:12]}", tofile=f"지금 판 {now[:12]}")
    print("\n".join(diff))


def _cmd_preview(store: Store, args) -> None:
    result = preview.ensure(store.config, store, args.draft_id)
    print(("이미 있는 미리보기" if result["reused"] else "미리보기를 만들었다") + f": {args.draft_id}")
    for lang, url in result["urls"].items():
        print(f"{lang}  {url}")
    print("승인 대기가 끝나거나 내용이 바뀌면 이 주소는 사라진다.")


def _finish(store: Store, decision: decisions.Decision) -> None:
    for warning in decisions.finish(store.config, store, decision):
        print(f"주의: {warning}", file=sys.stderr)


def _cmd_approve(store: Store, args) -> None:
    decision = decisions.approve(store.config, store, args.draft_id)
    print(f"승인했다: {args.draft_id} (해시 {decision.hash[:12]})")
    print("다음 사이클(매일 14:00)에서 발행된다. 그 전에 내용이 바뀌면 승인은 풀린다.")
    _finish(store, decision)


def _cmd_reject(store: Store, args) -> None:
    decision = decisions.reject(store.config, store, args.draft_id, args.reason, drop=args.drop)
    print(f"{'접었다' if args.drop else '반려했다'}: {args.draft_id}")
    print(decisions.next_step(decision))
    _finish(store, decision)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="review", description="Huninn 초안 승인·반려")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="처리할 초안 목록")
    p.add_argument("--all", action="store_true", help="발행된 초안까지")
    p = sub.add_parser("show", help="초안 요약")
    p.add_argument("draft_id")
    p.add_argument("--body", action="store_true", help="한국어 본문까지 출력")
    p = sub.add_parser("diff", help="지난 반려 판과 지금 판의 차이")
    p.add_argument("draft_id")
    p.add_argument("--en", action="store_true", help="영어판을 비교")
    p = sub.add_parser("preview", help="승인 대기 초안의 미리보기 주소")
    p.add_argument("draft_id")
    p = sub.add_parser("approve", help="승인")
    p.add_argument("draft_id")
    p = sub.add_parser("reject", help="반려 (사유 필수)")
    p.add_argument("draft_id")
    p.add_argument("reason")
    p.add_argument("--drop", action="store_true", help="이 글감을 접는다: 반려 + 보류 + 글감 blocked")
    args = parser.parse_args(argv)

    store = Store(Config.from_env())
    handler = {"list": _cmd_list, "show": _cmd_show, "diff": _cmd_diff, "preview": _cmd_preview,
               "approve": _cmd_approve, "reject": _cmd_reject}[args.command]
    try:
        handler(store, args)
    except (StoreError, preview.PreviewError) as e:
        print(f"review: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
