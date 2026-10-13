"""승인 대기 초안의 미리보기 (docs/blogops.md 11절).

초안을 실제 사이트 템플릿으로 사이트 전체와 함께 빌드해 state/previews/<토큰>/ 에 둔다.
운영자가 폰에서 발행된 모습 그대로(글꼴, 다크 모드, 그림, 메뉴 이동) 읽고 승인하게 하려는 것이다.

- 토큰은 추측할 수 없는 폴더 이름이다. 주소를 아는 사람만 읽는다 (Caddy :8081 → preview.unattendant.dev)
- 승인 대기인 초안의 지금 버전만 둔다. 내용이 바뀌면(해시가 달라지면) 새 토큰이 나오고 옛 폴더는 지운다.
  그래서 링크가 보여 주는 내용과 승인 버튼이 승인할 내용은 늘 같은 버전이다
- state/previews/는 비공개다 (.gitignore, pre-commit 훅). 토큰은 meta.json에 있다
- minify하지 않는다. Hugo의 HTML minify는 <body> 태그를 지워 안내 띠를 넣을 수 없다
"""
from __future__ import annotations

import html
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import KST, Config, find_tool
from .store import STATUS_LABELS, Store

TOKEN_BYTES = 20  # 160비트. 40자 16진수
TOKEN_RE = re.compile(r"^[0-9a-f]{40}$")
BUILD_PREFIX = ".build-"  # 만드는 중인 폴더. 점으로 시작하니 Caddy가 내주지 않는다
BUILD_STALE_SECONDS = 600
BANNER = ('<div role="note" style="padding:6px 12px;background:#b45309;color:#fff;'
          'font:600 13px/1.5 system-ui,sans-serif;text-align:center">'
          '미승인 초안 미리보기 · 해시 {hash} · 발행 전이라 공개되지 않은 글이다</div>')


class PreviewError(Exception):
    pass


def page_url(config: Config, token: str, slug: str, lang: str = "ko") -> str:
    prefix = "" if lang == "ko" else "en/"
    return f"{config.preview_base_url.rstrip('/')}/{token}/{prefix}posts/{slug}/"


def _urls(config: Config, store: Store, draft_id: str, token: str) -> dict[str, str]:
    slug = store.meta(draft_id)["slug"]
    return {lang: page_url(config, token, slug, lang) for lang in store.draft_paths(draft_id)}


def current(config: Config, store: Store, draft_id: str) -> Optional[dict]:
    """지금 버전의 미리보기가 이미 있으면 정보를, 없으면 None. 빌드하지 않는다."""
    h = store.content_hash(draft_id)
    record = store.preview_record(draft_id)
    if not record or record.get("hash") != h or not TOKEN_RE.match(record.get("token", "")):
        return None
    slug = store.meta(draft_id)["slug"]
    if not (config.previews_dir / record["token"] / "posts" / slug / "index.html").exists():
        return None
    return {"draft_id": draft_id, "token": record["token"], "hash": h,
            "urls": _urls(config, store, draft_id, record["token"])}


def ensure(config: Config, store: Store, draft_id: str) -> dict:
    """승인 대기 초안의 미리보기를 돌려준다. 지금 버전의 것이 있으면 그대로, 없으면 빌드한다."""
    status = store.status(draft_id)
    if status != "awaiting_approval":
        raise PreviewError(f"승인 대기 중인 초안만 미리볼 수 있다 (지금: {STATUS_LABELS[status]})")
    found = current(config, store, draft_id)
    if found:
        return {**found, "reused": True}
    h = store.content_hash(draft_id)
    token = secrets.token_hex(TOKEN_BYTES)
    _render(config, store, draft_id, token, h)
    store.set_preview(draft_id, token, h)
    cleanup(config, store)  # 옛 버전의 폴더를 지운다
    return {"draft_id": draft_id, "token": token, "hash": h,
            "urls": _urls(config, store, draft_id, token), "reused": False}


def _render(config: Config, store: Store, draft_id: str, token: str, h: str) -> None:
    binary = find_tool("hugo")
    site = config.site_dir
    if not binary:
        raise PreviewError("hugo가 없어 미리보기를 만들지 못했다")
    if not (site / "hugo.toml").exists():
        raise PreviewError(f"사이트 폴더를 찾을 수 없다: {site}")
    slug = store.meta(draft_id)["slug"]
    # Hugo는 실제 현재 시각보다 미래인 글을 빼므로, 설정 시계가 아니라 벽시계 기준으로 넣는다
    stamp = (datetime.now(KST) - timedelta(minutes=1)).isoformat(timespec="seconds")
    previews = config.previews_dir
    previews.mkdir(parents=True, exist_ok=True)
    out = previews / f"{BUILD_PREFIX}{token}"
    try:
        with tempfile.TemporaryDirectory(prefix="blogops-preview-") as tmp:
            content = Path(tmp) / "content"
            shutil.copytree(site / "content", content)
            dst = content / "posts" / slug
            dst.mkdir(parents=True, exist_ok=True)
            for path in store.draft_paths(draft_id).values():
                text = path.read_text(encoding="utf-8").replace("---\n", f'---\ndate: "{stamp}"\n', 1)
                (dst / path.name).write_text(text, encoding="utf-8")
            for path in store.asset_paths(draft_id):
                shutil.copy2(path, dst / path.name)
            base = f"{config.preview_base_url.rstrip('/')}/{token}/"
            result = subprocess.run(
                [binary, "--source", str(site), "--contentDir", str(content), "--destination", str(out),
                 "--baseURL", base, "--quiet"],
                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise PreviewError(f"미리보기 빌드가 실패했다: {(result.stderr or result.stdout).strip()[-400:]}")
        langs = sorted(store.draft_paths(draft_id))
        missing = [lang for lang in langs
                   if not (out / ("" if lang == "ko" else "en") / "posts" / slug / "index.html").exists()]
        if missing:
            raise PreviewError(f"빌드는 됐지만 글 페이지가 생기지 않았다: {', '.join(missing)}")
        if store.content_hash(draft_id) != h:
            raise PreviewError("미리보기를 만드는 동안 초안이 바뀌었다")
        _mark(out, slug, langs, h)
        os.replace(out, previews / token)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise


def _mark(out: Path, slug: str, langs: list[str], h: str) -> None:
    """초안 페이지 맨 위에 '미승인 초안' 띠를 넣는다. 사이트의 다른 페이지는 그대로 둔다."""
    banner = BANNER.format(hash=html.escape(h[:12]))
    for lang in langs:
        page = out / ("" if lang == "ko" else "en") / "posts" / slug / "index.html"
        text = page.read_text(encoding="utf-8")
        marked, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + banner, text, count=1)
        if n:  # 템플릿에 <body>가 없으면 띠만 빠진다. 미리보기 자체는 된다
            page.write_text(marked, encoding="utf-8")


def cleanup(config: Config, store: Store) -> list[str]:
    """승인 대기 초안의 지금 버전이 아닌 미리보기 폴더를 지운다. 지운 폴더 이름을 돌려준다."""
    previews = config.previews_dir
    if not previews.is_dir():
        return []
    keep = set()
    for d in store.list_drafts():
        if d["status"] == "awaiting_approval":
            record = store.preview_record(d["draft_id"])
            if record and record.get("hash") == d["hash"]:
                keep.add(record["token"])
    removed = []
    for path in sorted(previews.iterdir()):
        if path.is_symlink() or not path.is_dir():
            continue
        if path.name.startswith(BUILD_PREFIX):
            if time.time() - path.stat().st_mtime < BUILD_STALE_SECONDS:
                continue  # 지금 만드는 중일 수 있다
        elif path.name in keep:
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path.name)
    return removed
