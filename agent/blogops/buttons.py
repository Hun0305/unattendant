"""#승인 메시지의 버튼 (docs/blogops.md 11절).

notify가 REST로 메시지를 보낼 때 버튼 정보(components)를 붙이고, 봇(bot.py)이 클릭을 받는다.
둘이 같은 형식을 쓰도록 discord.py 없이 여기 모았다.

custom_id = bo:<동작>:<초안ID>:<해시 12자>   (디스코드 한도 100자. 슬러그 60자여도 93자)
    approve·reject·drop  메시지의 버튼    승인 / 반려(사유 입력) / 접기(반려 + 보류 + 글감 blocked)
    yes·no               승인 확인 메시지  확정 / 취소
해시는 버튼이 만들어질 때 사람이 보게 될 초안의 버전이다. 눌렀을 때 초안이 바뀌었으면 거부한다.
"""
from __future__ import annotations

import re
from typing import Optional

ACTIONS = ("approve", "reject", "drop", "yes", "no")
CUSTOM_ID_TEMPLATE = (r"bo:(?P<action>approve|reject|drop|yes|no)"
                      r":(?P<draft>\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*):(?P<hash>[0-9a-f]{12})")
CUSTOM_ID_RE = re.compile(CUSTOM_ID_TEMPLATE)
HASH_LEN = 12

PRIMARY, SECONDARY, SUCCESS, DANGER, LINK = 1, 2, 3, 4, 5  # 디스코드 버튼 스타일
LABELS = {"approve": "승인", "reject": "반려", "drop": "접기", "yes": "승인 확정", "no": "취소"}
STYLES = {"approve": SUCCESS, "reject": DANGER, "drop": SECONDARY, "yes": SUCCESS, "no": SECONDARY}


def custom_id(action: str, draft_id: str, content_hash: str) -> str:
    if action not in ACTIONS:
        raise ValueError(f"동작은 {', '.join(ACTIONS)} 중 하나다: {action!r}")
    value = f"bo:{action}:{draft_id}:{content_hash[:HASH_LEN]}"
    if not CUSTOM_ID_RE.fullmatch(value) or len(value) > 100:
        raise ValueError(f"버튼 ID 형식이 아니다: {value!r}")
    return value


def parse(value: str) -> Optional[tuple[str, str, str]]:
    """(동작, 초안ID, 해시 12자). 우리 버튼이 아니면 None."""
    match = CUSTOM_ID_RE.fullmatch(value or "")
    return (match["action"], match["draft"], match["hash"]) if match else None


def approval_components(draft_id: str, content_hash: str, preview_urls: Optional[dict] = None) -> list[dict]:
    """#승인 메시지 아래 버튼 한 줄: [미리보기] [영어판] [승인] [반려] [접기] (최대 5개)."""
    row = []
    urls = preview_urls or {}
    if urls.get("ko"):
        row.append({"type": 2, "style": LINK, "label": "미리보기", "url": urls["ko"]})
    if urls.get("en"):
        row.append({"type": 2, "style": LINK, "label": "영어판", "url": urls["en"]})
    for action in ("approve", "reject", "drop"):
        row.append({"type": 2, "style": STYLES[action], "label": LABELS[action],
                    "custom_id": custom_id(action, draft_id, content_hash)})
    return [{"type": 1, "components": row}]
