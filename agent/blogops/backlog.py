"""글감 백로그 (state/backlog.json). 공개 파일이고 Huninn이 주인이다."""
from __future__ import annotations

import re
from typing import Optional

from .config import SERIES, Config
from .fileio import read_json, state_lock, write_json

STATUSES = ("idea", "blocked", "drafting", "published", "dropped")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BacklogError(Exception):
    pass


def _path(config: Config):
    return config.state_dir / "backlog.json"


def load(config: Config) -> dict:
    data = read_json(_path(config))
    if data is None:
        raise BacklogError(f"백로그 파일이 없다: {_path(config)}")
    return data


def items(config: Config, status: Optional[str] = None) -> list[dict]:
    found = load(config)["items"]
    return [i for i in found if status is None or i["status"] == status]


def _save(config: Config, data: dict) -> None:
    data["updated"] = config.now().date().isoformat()
    write_json(_path(config), data)


def set_status(config: Config, item_id: str, status: str, note: Optional[str] = None) -> dict:
    if status not in STATUSES:
        raise BacklogError(f"상태는 {', '.join(STATUSES)} 중 하나다: {status!r}")
    if status in ("blocked", "dropped") and not (note or "").strip():
        raise BacklogError(f"{status}로 바꿀 때는 이유(note)가 필요하다")
    with state_lock(config):
        data = load(config)
        item = next((i for i in data["items"] if i["id"] == item_id), None)
        if item is None:
            raise BacklogError(f"없는 글감이다: {item_id}")
        item["status"] = status
        if note:
            item["notes"] = f"{item.get('notes', '')} [{config.now():%Y-%m-%d}] {note.strip()}".strip()
        _save(config, data)
    return item


def add_item(config: Config, *, item_id: str, title: str, series: str, notes: str = "",
             sources: Optional[list[str]] = None, added_by: str = "huninn") -> dict:
    if not ID_RE.match(item_id or ""):
        raise BacklogError(f"글감 ID는 소문자·숫자·하이픈이다: {item_id!r}")
    if series not in SERIES:
        raise BacklogError(f"없는 시리즈다: {series!r}")
    if not title.strip():
        raise BacklogError("제목이 필요하다")
    with state_lock(config):
        data = load(config)
        if any(i["id"] == item_id for i in data["items"]):
            raise BacklogError(f"같은 ID의 글감이 이미 있다: {item_id}")
        item = {"id": item_id, "title": title.strip(), "series": series, "status": "idea",
                "sources": list(sources or []), "notes": notes.strip(),
                "added": config.now().date().isoformat(), "added_by": added_by}
        data["items"].append(item)
        _save(config, data)
    return item
