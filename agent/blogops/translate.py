"""발행된 글에 영어판 붙이기 (docs/blogops.md 5절).

한국어판만 사람이 승인한다. 발행 직후 Huninn이 같은 글의 영어판을 써서 이 모듈로 붙인다.
승인 단계가 없는 대신 영어판도 품질 검사(분량, 비밀값, 개인정보, 링크, 빌드)를 거친다.

1. 사이트에 Huninn이 발행한 한국어판이 있고 영어판은 아직 없는지
2. 영어판 검사 (publish와 quality의 검사를 그대로 쓴다)
3. index.en.md를 쓴다. date·series·sources는 한국어판에서 가져온다 (두 판이 같아야 한다)
4. 임시 빌드 → 실제 빌드 → 커밋(작성자 Huninn) → push → 공개 URL 확인. 실패하면 되돌린다
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from . import frontmatter, log, publish, quality, records
from .config import Config
from .publish import PublishError, Verify


def read_post(config: Config, slug: str, lang: str = "ko") -> dict:
    """발행된 글의 front matter와 본문. 영어판을 쓰려고 한국어판을 읽을 때 쓴다."""
    path = _post_dir(config, slug) / f"index.{lang}.md"
    if not path.exists():
        raise PublishError(f"{lang}판이 없다: {slug}")
    fields, body = _read(path)
    return {"slug": slug, "lang": lang, "title": fields.get("title"), "description": fields.get("description"),
            "tags": fields.get("tags"), "series": fields.get("series"), "date": fields.get("date"),
            "sources": fields.get("sources") or [], "body": body,
            "figures": sorted(p.name for p in path.parent.iterdir() if p.suffix.lower() in FIGURE_SUFFIXES),
            "has_en": (path.parent / "index.en.md").exists()}


def _read(path: Path) -> tuple[dict, str]:
    # 사람이 쓴 글은 date가 JSON이 아닐 수 있어 느슨하게 읽는다
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---\n", 3)
    return records._loose_front_matter(text), text[end + 5:].lstrip("\n") if end != -1 else text


FIGURE_SUFFIXES = (".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif")


def _post_dir(config: Config, slug: str):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug or ""):
        raise PublishError(f"슬러그 형식이 아니다: {slug!r}")
    return config.site_dir / "content" / "posts" / slug


def add_english(config: Config, slug: str, *, title: str, description: str, tags: list[str], body: str,
                verify: Verify | None = None, scan=None) -> dict:
    post = _post_dir(config, slug)
    ko_path, en_path = post / "index.ko.md", post / "index.en.md"
    if not ko_path.exists():
        raise PublishError(f"발행된 한국어판이 없다: {slug}")
    if en_path.exists():
        raise PublishError(f"영어판이 이미 있다: {slug}")
    ko, _ = _read(ko_path)
    if ko.get("author") == "human":
        raise PublishError("운영자가 쓴 글의 영어판은 Huninn이 붙이지 않는다")

    fields = {"title": title.strip(), "description": description.strip(), "series": ko.get("series"),
              "tags": list(tags or []), "date": ko["date"]}
    if ko.get("sources"):
        fields["sources"] = ko["sources"]
    text = frontmatter.render(fields, body)

    problems = _problems(config, post, fields, body, text, scan)
    if problems:
        raise PublishError("영어판 검사를 통과하지 못했다: " + " / ".join(problems))

    en_path.write_text(text, encoding="utf-8")
    try:
        publish._build(config.site_dir, slug, ["ko", "en"])
        commit = publish._commit(config.site_dir, slug, _commit_message(slug, fields["title"], ko))
    except Exception:
        en_path.unlink(missing_ok=True)
        publish._git(config.site_dir, "reset", "-q", "--", f"content/posts/{slug}")
        publish._real_build(config.site_dir)
        raise

    warnings = []
    pushed = publish._push(config.site_dir)
    if not pushed:
        warnings.append("push하지 못했다. 영어판은 사이트에 올라갔지만 GitHub에는 아직 없다")
    url = f"{records.site_base_url(config)}/en/posts/{slug}/"
    verified = (verify or publish.verify_url)(url, fields["title"])
    if not verified:
        warnings.append(f"공개 URL에서 영어판을 확인하지 못했다: {url}")
    record = {"at": config.now().isoformat(timespec="seconds"), "url": url, "commit": commit,
              "pushed": pushed, "verified": verified}
    log.append(config, "add_english", "huninn", slug=slug, warnings=warnings, **record)
    return {**record, "slug": slug, "warnings": warnings}


def _problems(config: Config, post, fields: dict, body: str, text: str, scan) -> list[str]:
    problems = []
    for key in ("title", "description"):
        if not fields[key]:
            problems.append(f"{key}가 비어 있다")
    if not fields["tags"]:
        problems.append("tags가 없다")
    size = len(body.strip())
    if size < config.en_body_min_chars:
        problems.append(f"영어 본문이 짧다: {size}자 (최소 {config.en_body_min_chars}자)")
    if re.search(r"^# \S", re.sub(r"```.*?```", "", body, flags=re.S), re.M):
        problems.append("본문에 # 제목(h1)이 있다. 소제목은 ##부터 쓴다")
    # 그림은 한국어판이 쓰는 파일만 가리킬 수 있고, 설명(caption, 그림 파일이 SVG가 아니면 alt)이 있어야 한다
    for match in quality.FIG_RE.finditer(body):
        attrs = dict(quality.FIG_ATTR_RE.findall(match.group(1)))
        src = attrs.get("src", "")
        if not (post / src).is_file():
            problems.append(f"그림 파일이 글 폴더에 없다: {src!r}")
        elif not attrs.get("caption", "").strip():
            problems.append(f"그림에 caption이 없다: {src}")
        elif not src.lower().endswith(".svg") and not attrs.get("alt", "").strip():
            problems.append(f"그림에 alt가 없다: {src}")
    if re.search(r"\d", quality._prose(body)) and not fields.get("sources"):
        problems.append("본문에 숫자가 있는데 출처(sources)가 없다 (한국어판에도 없다)")
    urls = quality.LINK_RE.findall(body)
    for source in fields.get("sources") or []:
        urls.append(str(source.get("url", "")))
    for url in dict.fromkeys(urls):
        problems += quality._check_repo_link(config, url)
    problems += quality._post_link_problems(config, [body])
    problems += quality._privacy_problems(f"{fields['title']}\n{fields['description']}\n{body}")
    # 비밀값 검사는 임시 파일로 한다 (글 폴더를 건드리지 않는다)
    with tempfile.TemporaryDirectory(prefix="blogops-en-") as tmp:
        tmp_file = Path(tmp) / "index.en.md"
        tmp_file.write_text(text, encoding="utf-8")
        problems += (scan or quality.scan_files)(config, [tmp_file])
    return problems


def _commit_message(slug: str, title: str, ko: dict) -> str:
    return (f"content(ai): {title} (영어판)\n\n"
            f"- content/posts/{slug}/index.en.md 추가: 승인·발행된 한국어판의 영어판\n\n"
            f"왜: 한국어판만 사람이 승인하고, 영어판은 발행 직후 Huninn이 이어서 붙인다 (전략 v4)\n"
            f"확인: 영어판 검사 통과(분량·링크·개인정보·비밀값), 임시 빌드 성공\n")
