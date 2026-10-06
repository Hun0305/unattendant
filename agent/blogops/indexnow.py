"""IndexNow 색인 요청 (Bing, 네이버 등 참여 검색엔진).

키 파일은 사이트 루트에 공개로 둔다: site/static/<키>.txt (내용도 키). 비밀값이 아니다.
IndexNow가 이 파일을 가져가 우리 사이트의 요청인지 확인한다.
"""
from __future__ import annotations

import re
import secrets
from typing import Optional
from urllib.parse import urlparse

from . import log, records
from .config import Config
from .httpjson import Transport, post_json

ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_URLS = 100


class IndexNowError(Exception):
    pass


def find_key(config: Config) -> Optional[str]:
    static = config.site_dir / "static"
    if not static.is_dir():
        return None
    for path in sorted(static.glob("*.txt")):
        if KEY_RE.match(path.stem) and path.read_text(encoding="utf-8").strip() == path.stem:
            return path.stem
    return None


def create_key(config: Config) -> str:
    """키 파일을 만든다. 한 번만 쓰고, 사이트 레포에 커밋해 배포해야 효력이 생긴다."""
    existing = find_key(config)
    if existing:
        return existing
    key = secrets.token_hex(16)
    (config.site_dir / "static").mkdir(parents=True, exist_ok=True)
    (config.site_dir / "static" / f"{key}.txt").write_text(key + "\n", encoding="utf-8")
    return key


def request_indexing(config: Config, urls: list[str], transport: Transport | None = None) -> dict:
    key = find_key(config)
    if not key:
        raise IndexNowError("IndexNow 키 파일이 없다 (site/static/<키>.txt)")
    base = records.site_base_url(config)
    urls = list(dict.fromkeys(u.strip() for u in urls if u and u.strip()))
    if not urls:
        raise IndexNowError("요청할 URL이 없다")
    if len(urls) > MAX_URLS:
        raise IndexNowError(f"한 번에 {MAX_URLS}개까지다")
    foreign = [u for u in urls if not u.startswith(base + "/")]
    if foreign:
        raise IndexNowError(f"우리 사이트 주소가 아니다: {', '.join(foreign)}")
    payload = {"host": urlparse(base).hostname, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}
    status, body = (transport or post_json)(ENDPOINT, {"User-Agent": "Huninn-blogops/0.1"}, payload)
    log.append(config, "request_indexing", "huninn", urls=urls, status=status)
    if status not in (200, 202):
        raise IndexNowError(f"IndexNow 요청이 거절됐다: HTTP {status} {body.get('message', '')}".strip())
    return {"status": status, "urls": urls}
