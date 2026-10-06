"""Huninn이 읽을 수 있는 공개 기록 (docs/blogops.md 2절).

Huninn에게는 Read 도구가 없다(ops/huninn/settings.json). 운영기의 재료는 이 모듈로만 읽는다.
- read_record: 허용 목록에 있는 공개 문서만. .env, logs/, state/drafts/ 같은 경로는 열 수 없다
- git_log: 커밋 메시지만. 변경 내용(diff)은 주지 않는다
- site_posts: 발행된 글의 제목·날짜·시리즈 (중복 확인과 list_posts용)
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from .config import Config

# 레포 루트 기준 경로. site/로 시작하면 사이트 레포 기준이다
ALLOWED_RECORDS = ("docs/*.md", "ops/README.md", "site/README.md")
READ_LIMIT = 12000  # 한 번에 돌려주는 글자 수
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RecordError(Exception):
    pass


def _base_and_rel(config: Config, path: PurePosixPath) -> tuple[Path, PurePosixPath]:
    if path.parts[0] == "site":
        return config.site_dir, PurePosixPath(*path.parts[1:])
    return config.root, path


def _resolve(config: Config, path: str) -> Path:
    p = PurePosixPath(path or "")
    if not path or p.is_absolute() or ".." in p.parts:
        raise RecordError(f"읽을 수 없는 경로다: {path!r}")
    if not any(fnmatch.fnmatchcase(str(p), pattern) for pattern in ALLOWED_RECORDS):
        raise RecordError(f"공개 기록 목록에 없는 경로다: {path} (가능: {', '.join(ALLOWED_RECORDS)})")
    base, rel = _base_and_rel(config, p)
    full = (base / rel).resolve()
    # 심볼릭 링크를 따라간 실제 위치도 레포 안, 허용 목록 안이어야 한다 (예: docs/x.md → .env 차단)
    if not full.is_relative_to(base.resolve()):
        raise RecordError(f"읽을 수 없는 경로다: {path}")
    real = PurePosixPath(full.relative_to(base.resolve()).as_posix())
    if p.parts[0] == "site":
        real = PurePosixPath("site") / real
    if not any(fnmatch.fnmatchcase(str(real), pattern) for pattern in ALLOWED_RECORDS):
        raise RecordError(f"읽을 수 없는 경로다: {path}")
    if not full.is_file():
        raise RecordError(f"없는 파일이다: {path}")
    return full


def list_records(config: Config) -> list[dict]:
    found = []
    for pattern in ALLOWED_RECORDS:
        p = PurePosixPath(pattern)
        base, rel = _base_and_rel(config, p)
        for full in sorted(base.glob(str(rel))):
            logical = str(PurePosixPath(*p.parts[:1]) / full.relative_to(base)) if p.parts[0] == "site" \
                else str(full.relative_to(base))
            try:
                full = _resolve(config, logical)
            except RecordError:
                continue
            text = full.read_text(encoding="utf-8")
            title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), "")
            found.append({"path": logical, "title": title, "chars": len(text)})
    return found


def read_record(config: Config, path: str, offset: int = 0) -> dict:
    text = _resolve(config, path).read_text(encoding="utf-8")
    offset = max(0, int(offset))
    chunk = text[offset:offset + READ_LIMIT]
    end = offset + len(chunk)
    return {"path": path, "total_chars": len(text), "offset": offset, "text": chunk,
            "next_offset": end if end < len(text) else None}


def git_log(config: Config, repo: str = "ops", since: str | None = None, limit: int = 30) -> list[dict]:
    if repo not in ("ops", "site"):
        raise RecordError(f"레포는 ops 또는 site다: {repo!r}")
    if since is not None and not DATE_RE.match(since):
        raise RecordError(f"since는 YYYY-MM-DD 형식이다: {since!r}")
    limit = max(1, min(int(limit), 100))
    path = config.root if repo == "ops" else config.site_dir
    args = ["git", "-C", str(path), "log", f"-n{limit}", "--format=%H%x1f%aI%x1f%an%x1f%s%x1f%b%x1e"]
    if since:
        args.append(f"--since={since} 00:00:00 +0900")
    out = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout
    commits = []
    for raw in out.split("\x1e"):
        if not raw.strip():
            continue
        sha, date, author, subject, body = raw.strip("\n").split("\x1f", 4)
        body = "\n".join(line for line in body.splitlines() if not line.startswith("Co-Authored-By:")).strip()
        commits.append({"commit": sha[:12], "date": date, "author": author, "subject": subject, "body": body[:2000]})
    return commits


def search_posts(config: Config, query: str, limit: int = 10) -> list[dict]:
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []
    results = []
    for post in site_posts(config):
        path = config.site_dir / "content" / "posts" / post["slug"] / f"index.{post['lang']}.md"
        text = path.read_text(encoding="utf-8")
        haystack = f"{post['title']}\n{post['description']}\n{text}".lower()
        score = sum(haystack.count(t) for t in terms) + 5 * sum(t in post["title"].lower() for t in terms)
        if score:
            results.append({**{k: post[k] for k in ("slug", "lang", "title", "date", "series")}, "score": score})
    return sorted(results, key=lambda r: -r["score"])[:limit]


def site_base_url(config: Config) -> str:
    m = re.search(r'^baseURL\s*=\s*"([^"]+)"', (config.site_dir / "hugo.toml").read_text(encoding="utf-8"), re.M)
    return (m.group(1) if m else "https://unattendant.dev/").rstrip("/")


def _loose_front_matter(text: str) -> dict:
    # 사람이 쓴 글은 date: 2026-10-06T20:34:00+09:00 처럼 JSON이 아닌 값도 있어 느슨하게 읽는다
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 3)
    fields = {}
    for line in text[4:end if end != -1 else len(text)].splitlines():
        key, sep, value = line.partition(":")
        if not sep or line.startswith((" ", "#")):
            continue
        value = value.strip()
        try:
            fields[key.strip()] = json.loads(value)
        except ValueError:
            fields[key.strip()] = value.strip("'\"")
    return fields


def site_posts(config: Config) -> list[dict]:
    posts_dir = config.site_dir / "content" / "posts"
    if not posts_dir.is_dir():
        return []
    posts = []
    for bundle in sorted(p for p in posts_dir.iterdir() if p.is_dir()):
        for lang in ("ko", "en"):
            path = bundle / f"index.{lang}.md"
            if not path.exists():
                continue
            fields = _loose_front_matter(path.read_text(encoding="utf-8"))
            series = fields.get("series") or []
            posts.append({"slug": bundle.name, "lang": lang, "title": str(fields.get("title", "")),
                          "date": str(fields.get("date", "")), "description": str(fields.get("description", "")),
                          "series": series if isinstance(series, list) else [series],
                          "author": fields.get("author", "huninn")})
    return posts
