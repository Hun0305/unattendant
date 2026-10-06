"""품질 검사 (docs/blogops.md 6절).

자동으로 확인할 수 있는 것만 본다. 사실이 맞는지는 사람이 승인할 때 본다.
검사 결과는 지금 내용의 해시와 함께 기록되고, 서로 다른 버전으로 연달아
max_quality_failures번 실패하면 초안을 보류한다.
"""
from __future__ import annotations

import difflib
import ipaddress
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from . import frontmatter, log, records
from .config import CURRENT_SERIES, KST, Config, find_tool
from .store import Store

IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_RE = re.compile(r"(?<![0-9A-Fa-f:-])[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}(?![0-9A-Fa-f:-])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ALLOWED_EMAILS = re.compile(r"(?:noreply@anthropic\.com|huninn@unattendant\.dev|.*@users\.noreply\.github\.com)$")
LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")
REPO_URL_RE = re.compile(r"^https://github\.com/Hun0305/(unattendant\.dev|unattendant)/(?:blob|tree)/[^/]+/([^#?]+)")
TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")
# 초안에 쓰지 않는 front matter. date·lastmod는 발행할 때 넣고, author·translation·sponsored는 사람만 쓴다
FORBIDDEN_FIELDS = ("date", "lastmod", "draft", "author", "translation", "sponsored")
SIMILAR_TITLE = 0.85

Check = Callable[[Config, Store, str], list[str]]


def check_quality(config: Config, store: Store, draft_id: str,
                  scan: Check | None = None, build: Check | None = None) -> dict:
    problems = run_checks(config, store, draft_id, scan=scan or gitleaks_scan, build=build or hugo_build)
    record = store.record_quality(draft_id, not problems, problems)
    held = False
    if problems:
        failures = store.consecutive_quality_failures(draft_id)
        if failures >= config.max_quality_failures:
            store.mark_held(draft_id, f"품질 검사를 {failures}번 연달아 통과하지 못했다: {problems[0]}")
            held = True
    log.append(config, "check_quality", "huninn", draft_id=draft_id, passed=not problems,
               problems=problems, hash=record["hash"], held=held)
    return {"draft_id": draft_id, "passed": not problems, "problems": problems, "held": held}


def run_checks(config: Config, store: Store, draft_id: str, scan: Check, build: Check) -> list[str]:
    problems: list[str] = []
    meta = store.meta(draft_id)
    series = meta["series"]
    parsed: dict[str, tuple[dict, str]] = {}
    for lang, path in store.draft_paths(draft_id).items():
        try:
            parsed[lang] = frontmatter.parse(path.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{lang}판 front matter를 읽을 수 없다: {e}")
    if "ko" not in parsed:
        return problems or ["한국어판이 없다"]

    # front matter
    for lang, (fields, body) in parsed.items():
        for key in ("title", "description"):
            if not str(fields.get(key) or "").strip():
                problems.append(f"{lang}판 {key}가 비어 있다")
        if fields.get("series") != [series]:
            problems.append(f"{lang}판 series가 {series}가 아니다: {fields.get('series')}")
        if not fields.get("tags"):
            problems.append(f"{lang}판 tags가 없다")
        for key in FORBIDDEN_FIELDS:
            if key in fields:
                problems.append(f"{lang}판에 {key}를 쓰지 않는다 (date는 발행할 때 넣고, author·translation·sponsored는 사람만 쓴다)")

    # 시리즈와 영어판
    if series not in CURRENT_SERIES:
        problems.append(f"지금 단계에서 쓸 수 있는 시리즈가 아니다: {series} (가능: {', '.join(CURRENT_SERIES)})")
    if series == "weekly-report" and "en" not in parsed:
        problems.append("주간 보고서는 영어판(index.en.md)도 있어야 한다")

    # 분량
    ko_len = len(parsed["ko"][1].strip())
    if ko_len < config.body_min_chars:
        problems.append(f"한국어 본문이 짧다: {ko_len}자 (최소 {config.body_min_chars}자)")
    if ko_len > config.body_max_chars:
        problems.append(f"한국어 본문이 길다: {ko_len}자 (최대 {config.body_max_chars}자)")
    if "en" in parsed and len(parsed["en"][1].strip()) < config.en_body_min_chars:
        problems.append(f"영어 본문이 짧다: {len(parsed['en'][1].strip())}자 (최소 {config.en_body_min_chars}자)")

    # 출처와 링크
    sources = parsed["ko"][0].get("sources") or []
    bodies = {lang: body for lang, (_, body) in parsed.items()}
    if any(re.search(r"\d", _prose(body)) for body in bodies.values()) and not sources:
        problems.append("본문에 숫자가 있는데 출처(sources)가 없다")
    for source in sources:
        if not isinstance(source, dict) or not source.get("title") or not re.match(r"^https?://", str(source.get("url", ""))):
            problems.append(f"출처는 title과 http(s) url이 있어야 한다: {source}")
    urls = [str(s.get("url")) for s in sources if isinstance(s, dict)]
    for body in bodies.values():
        urls += LINK_RE.findall(body)
    for url in dict.fromkeys(urls):
        problems += _check_repo_link(config, url)

    # 쓰지 않는 것: 내부 IP·MAC 주소, 이메일
    texts = [f"{f.get('title', '')}\n{f.get('description', '')}\n{b}" for f, b in parsed.values()]
    problems += _privacy_problems("\n".join(texts))

    # 중복
    existing = records.site_posts(config)
    if any(p["slug"] == meta["slug"] for p in existing):
        problems.append(f"같은 슬러그의 글이 이미 있다: {meta['slug']}")
    for lang, (fields, _) in parsed.items():
        title = str(fields.get("title", ""))
        for post in existing:
            if post["lang"] == lang and difflib.SequenceMatcher(None, title, post["title"]).ratio() >= SIMILAR_TITLE:
                problems.append(f"{lang}판 제목이 기존 글과 거의 같다: {post['title']} (/posts/{post['slug']}/)")

    # 비밀값과 빌드 (외부 도구)
    problems += scan(config, store, draft_id)
    if not problems:  # 다른 문제가 없을 때만 빌드한다 (느리고, 문제를 고치면 어차피 다시 검사한다)
        problems += build(config, store, draft_id)
    return problems


def _prose(body: str) -> str:
    # 숫자 검사용: 코드 블록, 인라인 코드, 링크 주소, 맨 URL을 뺀 문장
    text = re.sub(r"```.*?```", " ", body, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    return re.sub(r"https?://\S+", " ", text)


def _check_repo_link(config: Config, url: str) -> list[str]:
    m = REPO_URL_RE.match(url)
    if not m:
        return []
    repo, rel = m.groups()
    base = config.site_dir if repo == "unattendant.dev" else config.root
    target = (base / rel).resolve()
    if not target.is_relative_to(base.resolve()) or not target.exists():
        return [f"링크한 파일이 레포에 없다: {url}"]
    return []


def _privacy_problems(text: str) -> list[str]:
    problems = []
    for m in dict.fromkeys(IP_RE.findall(text)):
        try:
            ip = ipaddress.ip_address(m)
        except ValueError:
            continue
        if (ip.is_private and not ip.is_loopback) or ip in TAILSCALE_NET:
            problems.append(f"내부 IP 주소가 있다: {m}")
    for m in dict.fromkeys(MAC_RE.findall(text)):
        problems.append(f"MAC 주소로 보이는 값이 있다: {m}")
    for m in dict.fromkeys(EMAIL_RE.findall(text)):
        if not ALLOWED_EMAILS.match(m):
            problems.append(f"이메일 주소가 있다: {m}")
    return problems


def gitleaks_scan(config: Config, store: Store, draft_id: str) -> list[str]:
    binary = find_tool("gitleaks")
    if not binary:
        return ["gitleaks가 없어 비밀값 검사를 하지 못했다 (ops/install-gitleaks.sh)"]
    with tempfile.TemporaryDirectory(prefix="blogops-scan-") as tmp:
        tmp_path = Path(tmp)
        files = tmp_path / "files"
        files.mkdir()
        for path in store.draft_paths(draft_id).values():  # 글 파일만 검사한다 (meta.json의 해시는 빼고)
            shutil.copy2(path, files / path.name)
        report = tmp_path / "report.json"
        result = subprocess.run(
            [binary, "dir", "--no-banner", "--redact", "--log-level", "error", "--config", str(config.gitleaks_config),
             "--report-format", "json", "--report-path", str(report), str(files)],
            capture_output=True, text=True, timeout=180)
        if result.returncode not in (0, 1) or not report.exists():
            return [f"비밀값 검사를 실행하지 못했다: {result.stderr.strip()[-300:]}"]
        findings = json.loads(report.read_text() or "[]")
    return [f"비밀값으로 보이는 내용이 있다: {f.get('RuleID')} ({Path(f.get('File', '')).name} {f.get('StartLine')}줄)"
            for f in findings]


def hugo_build(config: Config, store: Store, draft_id: str) -> list[str]:
    binary = find_tool("hugo")
    site = config.site_dir
    if not binary:
        return ["hugo가 없어 빌드 검사를 하지 못했다"]
    if not (site / "hugo.toml").exists():
        return [f"사이트 폴더를 찾을 수 없다: {site}"]
    slug = store.meta(draft_id)["slug"]
    # Hugo는 실제 현재 시각보다 미래인 글을 빼므로, 설정 시계가 아니라 벽시계 기준으로 넣는다
    stamp = (datetime.now(KST) - timedelta(minutes=1)).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory(prefix="blogops-build-") as tmp:
        tmp_path = Path(tmp)
        content = tmp_path / "content"
        shutil.copytree(site / "content", content)
        dst = content / "posts" / slug
        dst.mkdir(parents=True, exist_ok=True)
        for lang, path in store.draft_paths(draft_id).items():
            text = path.read_text(encoding="utf-8").replace("---\n", f'---\ndate: "{stamp}"\n', 1)
            (dst / path.name).write_text(text, encoding="utf-8")
        public = tmp_path / "public"
        result = subprocess.run([binary, "--source", str(site), "--contentDir", str(content),
                                 "--destination", str(public), "--quiet"],
                                capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            return [f"Hugo 빌드가 실패한다: {(result.stderr or result.stdout).strip()[-500:]}"]
        missing = [lang for lang in store.draft_paths(draft_id)
                   if not (public / ("" if lang == "ko" else "en") / "posts" / slug / "index.html").exists()]
        if missing:
            return [f"빌드는 됐지만 글 페이지가 생기지 않았다: {', '.join(missing)}"]
    return []
