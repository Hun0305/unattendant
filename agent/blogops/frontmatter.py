"""초안의 front matter 쓰기·읽기.

값은 JSON 문법으로 쓴다. JSON은 YAML의 부분집합이라 Hugo가 그대로 읽고,
PyYAML 없이 json 모듈만으로 다시 읽을 수 있다.
    title: "제목"
    tags: ["meta", "운영"]
"""
from __future__ import annotations

import json

ORDER = ("title", "description", "series", "tags", "sources")


def render(fields: dict, body: str) -> str:
    keys = [k for k in ORDER if k in fields] + sorted(k for k in fields if k not in ORDER)
    lines = ["---"]
    for key in keys:
        if fields[key] is not None:
            lines.append(f"{key}: {json.dumps(fields[key], ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def parse(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("front matter가 없다")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise ValueError("front matter가 닫히지 않았다")
    fields: dict = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"front matter 줄을 읽을 수 없다: {line!r}")
        fields[key.strip()] = json.loads(value.strip())
    return fields, text[end + 5:].lstrip("\n")
