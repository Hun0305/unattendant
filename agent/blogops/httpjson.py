"""JSON POST. 비밀값이 든 헤더는 오류 메시지에 담지 않는다."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

Transport = Callable[[str, dict, dict], tuple[int, dict]]


def post_json(url: str, headers: dict, payload: dict, timeout: float = 20) -> tuple[int, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _json(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _json(e.read())
    except OSError as e:
        return 0, {"message": f"연결 실패: {type(e).__name__}"}


def _json(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw or b"{}")
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}
