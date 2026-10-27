"""발행 (docs/blogops.md 5절).

1. 승인된 그 버전인지 (상태 approved = 마지막 승인의 해시가 지금 해시)
2. 품질 검사를 통과한 버전인지
3. 오늘(KST) Huninn이 발행한 글이 없는지
4. site/content/posts/<슬러그>/로 복사하고 date와 발행 기록(receipt)을 넣는다
5. 임시 폴더에 먼저 빌드하고, 성공하면 실제 public/을 빌드한다. 실패하면 되돌린다
6. 사이트 레포에 작성자 Huninn으로 커밋하고 push한다 (겹치면 rebase 후 한 번 더)
7. 공개 URL에서 200과 제목을 확인한다
8. 초안과 백로그를 published로 바꾼다
"""
from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import backlog, frontmatter, log, records, status
from .config import Config, find_tool
from .store import STATUS_LABELS, Store

HUNINN_NAME = "Huninn"
HUNINN_EMAIL = "huninn@unattendant.dev"


class PublishError(Exception):
    pass


Verify = Callable[[str, str], bool]


def publish_post(config: Config, store: Store, draft_id: str, verify: Verify | None = None) -> dict:
    status = store.status(draft_id)
    if status != "approved":
        raise PublishError(f"사람이 승인한 그 버전만 발행할 수 있다 (지금: {STATUS_LABELS[status]})")
    if not store.passed_quality(draft_id):
        raise PublishError("품질 검사를 통과한 버전이 아니다")
    meta = store.meta(draft_id)
    fields, _ = store.fields(draft_id, "ko")
    title = fields["title"]

    now = config.now()
    today = now.date().isoformat()
    mine_today = [p for p in records.site_posts(config)
                  if p["lang"] == "ko" and p["author"] != "human" and p["date"][:10] == today]
    if len(mine_today) >= config.daily_publish_limit:
        raise PublishError(f"오늘은 이미 발행했다: /posts/{mine_today[0]['slug']}/ (하루 {config.daily_publish_limit}편)")

    site = config.site_dir
    slug = meta["slug"]
    dst = site / "content" / "posts" / slug
    if dst.exists():
        raise PublishError(f"같은 슬러그의 글이 이미 있다: {slug}")
    stamp = now.isoformat(timespec="seconds")
    langs = sorted(store.draft_paths(draft_id))
    assets = [p.name for p in store.asset_paths(draft_id)]

    stamped = {"date": stamp, "receipt": receipt(store, draft_id, meta)}
    dst.mkdir(parents=True)
    try:
        for path in store.draft_paths(draft_id).values():
            fields, body = frontmatter.parse(path.read_text(encoding="utf-8"))
            (dst / path.name).write_text(frontmatter.render({**fields, **stamped}, body), encoding="utf-8")
        for path in store.asset_paths(draft_id):
            shutil.copy2(path, dst / path.name)
        _build(site, slug, langs)
        commit = _commit(site, slug, _commit_message(store, draft_id, meta, title, langs, assets))
    except Exception:
        shutil.rmtree(dst, ignore_errors=True)
        _git(site, "reset", "-q", "--", f"content/posts/{slug}")
        _real_build(site)  # 앞 상태로 다시 빌드 (실패해도 원래 오류를 알린다)
        raise

    warnings = []
    pushed = _push(site)
    if not pushed:
        warnings.append("push하지 못했다. 글은 사이트에 올라갔지만 GitHub에는 아직 없다")
    url = f"{records.site_base_url(config)}/posts/{slug}/"
    verified = (verify or verify_url)(url, title)
    if not verified:
        warnings.append(f"공개 URL에서 글을 확인하지 못했다: {url}")

    record = {"at": stamp, "url": url, "commit": commit, "pushed": pushed, "verified": verified,
              "hash": store.content_hash(draft_id)}
    store.mark_published(draft_id, record)
    if meta.get("backlog_id"):
        try:
            backlog.set_status(config, meta["backlog_id"], "published", note=url)
        except backlog.BacklogError as e:
            warnings.append(f"백로그를 바꾸지 못했다: {e}")
    log.append(config, "publish_post", "huninn", draft_id=draft_id, warnings=warnings, **record)
    return {**record, "draft_id": draft_id, "warnings": warnings}


def receipt(store: Store, draft_id: str, meta: dict) -> dict:
    """글 하단 "발행 기록"(사이트 layouts/_partials/post-receipt.html)에 공개하는 값.
    비공개 초안 기록(meta.json, 승인 기록)에서 날짜와 횟수만 꺼내고, 반려 사유 같은 글은 넣지 않는다.
    Pi 상태는 발행하는 순간에 직접 읽는다(status.json과 같은 함수). 읽지 못한 값은 뺀다."""
    decisions = store.decisions(draft_id)
    mem = status.memory_gb()
    record = {
        "cycle": os.environ.get("BLOGOPS_CYCLE_ID") or None,
        "model": meta.get("model"),
        "drafted": meta["created_at"],
        "quality_checks": len(meta.get("quality", [])),
        "rejections": sum(d["decision"] == "rejected" for d in decisions),
        "approved": decisions[-1]["at"],
        "cpu_temp_c": status.cpu_temp_c(),
        "mem_used_gb": mem[0] if mem else None,
        "mem_total_gb": mem[1] if mem else None,
    }
    return {k: v for k, v in record.items() if v is not None}


def _cycle_at(cycles: list[dict], ts: str) -> dict | None:
    """ts(ISO 시각)가 들어 있는 정규 사이클(started ≤ ts ≤ ts 기록 시각). 없으면 None."""
    when = datetime.fromisoformat(ts)
    for c in cycles:
        if c.get("dry_run") or not c.get("started"):
            continue
        if datetime.fromisoformat(c["started"]) <= when <= datetime.fromisoformat(c["ts"]):
            return c
    return None


def backfill_receipt(config: Config, store: Store, draft_id: str) -> dict:
    """receipt가 생기기 전(2026-10-27)에 발행된 글의 발행 기록을 남은 기록으로 다시 만든다.
    사이클과 모델은 logs/cycles.jsonl에서 발행·작성 시각이 들어 있는 사이클로 찾는다(손으로 돌린 때는 빠진다).
    발행하던 순간의 Pi 상태는 남아 있지 않아 넣지 않고, 나중에 채웠다는 표시(backfilled)를 단다."""
    meta = store.meta(draft_id)
    if not meta.get("published"):
        raise PublishError(f"발행되지 않은 초안이다: {draft_id}")
    cycles_file = config.logs_dir / "cycles.jsonl"
    cycles = []
    if cycles_file.exists():
        for line in cycles_file.read_text(encoding="utf-8").splitlines():
            try:
                cycles.append(json.loads(line))
            except ValueError:
                continue
    published = _cycle_at(cycles, meta["published"]["at"])
    drafted = _cycle_at(cycles, meta["created_at"])
    decisions = [d for d in store.decisions(draft_id) if d["at"] <= meta["published"]["at"]]
    record = {
        "cycle": published["cycle"] if published else None,
        "model": meta.get("model") or (drafted or {}).get("model"),
        "drafted": meta["created_at"],
        "quality_checks": len([q for q in meta.get("quality", []) if q["at"] <= meta["published"]["at"]]),
        "rejections": sum(d["decision"] == "rejected" for d in decisions),
        "approved": next((d["at"] for d in reversed(decisions) if d["decision"] == "approved"), None),
        "backfilled": config.now().date().isoformat(),
    }
    return {k: v for k, v in record.items() if v is not None}


def _hugo() -> str:
    binary = find_tool("hugo")
    if not binary:
        raise PublishError("hugo가 없다")
    return binary


def _build(site: Path, slug: str, langs: list[str]) -> None:
    with tempfile.TemporaryDirectory(prefix="blogops-publish-") as tmp:
        public = Path(tmp) / "public"
        result = subprocess.run([_hugo(), "--source", str(site), "--destination", str(public), "--quiet"],
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise PublishError(f"임시 빌드가 실패했다: {(result.stderr or result.stdout).strip()[-500:]}")
        missing = [lang for lang in langs
                   if not (public / ("" if lang == "ko" else "en") / "posts" / slug / "index.html").exists()]
        if missing:
            raise PublishError(f"임시 빌드에 글 페이지가 없다: {', '.join(missing)} (date가 미래인지 확인)")
    result = _real_build(site)
    if result.returncode != 0:
        raise PublishError(f"사이트 빌드가 실패했다: {(result.stderr or result.stdout).strip()[-500:]}")


def _real_build(site: Path) -> subprocess.CompletedProcess:
    # ops/README.md "사이트 빌드"와 같은 명령. Caddy가 public/을 바로 서빙한다
    return subprocess.run([_hugo(), "--source", str(site), "--gc", "--minify", "--cleanDestinationDir", "--quiet"],
                          capture_output=True, text=True, timeout=300)


def _git(site: Path, *args: str, author: bool = False, stdin: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(site)]
    if author:
        cmd += ["-c", f"user.name={HUNINN_NAME}", "-c", f"user.email={HUNINN_EMAIL}"]
    return subprocess.run(cmd + list(args), input=stdin, capture_output=True, text=True, timeout=180)


def _commit_message(store: Store, draft_id: str, meta: dict, title: str, langs: list[str],
                    assets: list[str]) -> str:
    # CLAUDE.md 커밋 규칙: content(ai), 본문에 무엇을·왜·어떻게 확인했는지
    approved = store.decisions(draft_id)[-1]
    quality = store.meta(draft_id)["quality"][-1]
    why = f"백로그 글감 {meta['backlog_id']}" if meta.get("backlog_id") else "백로그 밖 글감"
    return (f"content(ai): {title}\n\n"
            f"- content/posts/{meta['slug']}/: {meta['series']} 글 ({', '.join(langs)})\n"
            + (f"- 그림 {len(assets)}개: {', '.join(assets)}\n" if assets else "") +
            f"- 초안 {draft_id}, 해시 {approved['hash'][:12]}\n\n"
            f"왜: {why}\n"
            f"확인: 품질 검사 통과({quality['at']}), 운영자 승인({approved['at']}), 임시 빌드 성공\n")


def _commit(site: Path, slug: str, message: str) -> str:
    path = f"content/posts/{slug}"
    for args, kw in ((("add", "--", path), {}),
                     (("commit", "-q", "-F", "-", "--", path), {"author": True, "stdin": message})):
        result = _git(site, *args, **kw)
        if result.returncode != 0:
            raise PublishError(f"커밋하지 못했다 (git {args[0]}): {(result.stderr or result.stdout).strip()[-500:]}")
    return _git(site, "rev-parse", "--short=12", "HEAD").stdout.strip()


def _push(site: Path) -> bool:
    branch = _git(site, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if _git(site, "push", "-q", "origin", branch).returncode == 0:
        return True
    # 사람이 먼저 push했으면 받아서 내 커밋을 위에 얹고 한 번 더
    if _git(site, "pull", "-q", "--rebase", "origin", branch, author=True).returncode != 0:
        _git(site, "rebase", "--abort")
        return False
    _real_build(site)  # 받아 온 템플릿 변경을 반영한다
    return _git(site, "push", "-q", "origin", branch).returncode == 0


def verify_url(url: str, title: str, tries: int = 3, wait: float = 5.0) -> bool:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Huninn-blogops/0.1"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                # Hugo는 제목의 따옴표 등을 &#34;로 바꿔 쓰므로 원래 글자로 되돌려 비교한다
                body = html.unescape(resp.read().decode("utf-8", "replace"))
                if resp.status == 200 and title in body:
                    return True
        except OSError:
            pass
        if attempt < tries - 1:
            time.sleep(wait)
    return False
