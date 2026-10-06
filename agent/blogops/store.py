"""초안과 승인 기록 (docs/blogops.md 3절).

state/drafts/<초안ID>/
    index.ko.md, index.en.md   Hugo 글 형식 (front matter + 본문)
    meta.json                  작성·수정 이력, 품질 검사 기록, 승인 요청 기록, 보류, 발행
state/approvals/<초안ID>.json  사람의 승인·반려 기록

초안의 상태는 따로 저장하지 않고, 지금 내용의 해시와 기록을 대조해 그때그때 계산한다.
승인은 승인할 때의 해시에 묶이므로, 승인 뒤 내용이 한 글자라도 바뀌면 자동으로 풀린다.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable, Optional

from . import frontmatter
from .config import SERIES, Config
from .fileio import read_json as _read_json
from .fileio import state_lock
from .fileio import write_atomic as _write_atomic
from .fileio import write_json as _write_json

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DRAFT_ID_RE = re.compile(r"^\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGS = ("ko", "en")

STATUS_LABELS = {
    "writing": "작성 중",
    "ready": "품질 통과",
    "awaiting_approval": "승인 대기",
    "approved": "승인됨",
    "rejected": "반려됨",
    "held": "보류",
    "published": "발행됨",
}


class StoreError(Exception):
    """잘못된 요청. 메시지는 사람과 Huninn이 그대로 읽는다."""


class Store:
    def __init__(self, config: Config, now: Optional[Callable] = None):
        self.config = config
        self._now = now or config.now

    def _ts(self) -> str:
        return self._now().isoformat(timespec="seconds")

    def _lock(self):
        return state_lock(self.config)

    # ── 경로 ──────────────────────────────────────────────

    def _dir(self, draft_id: str) -> Path:
        if not DRAFT_ID_RE.match(draft_id or ""):
            raise StoreError(f"초안 ID 형식이 아니다: {draft_id!r} (예: 20261008-naming)")
        path = self.config.drafts_dir / draft_id
        if not path.is_dir():
            raise StoreError(f"없는 초안이다: {draft_id}")
        return path

    def _approval_path(self, draft_id: str) -> Path:
        return self.config.approvals_dir / f"{draft_id}.json"

    def draft_paths(self, draft_id: str) -> dict[str, Path]:
        d = self._dir(draft_id)
        return {lang: d / f"index.{lang}.md" for lang in LANGS if (d / f"index.{lang}.md").exists()}

    # ── 읽기 ──────────────────────────────────────────────

    def meta(self, draft_id: str) -> dict:
        return _read_json(self._dir(draft_id) / "meta.json")

    def decisions(self, draft_id: str) -> list[dict]:
        self._dir(draft_id)
        return _read_json(self._approval_path(draft_id), {"decisions": []})["decisions"]

    def content_hash(self, draft_id: str) -> str:
        # 글 파일(index.*.md)을 이름 순으로, 파일 이름까지 포함해 이어 붙인 SHA-256
        h = hashlib.sha256()
        for path in sorted(self._dir(draft_id).glob("index.*.md")):
            h.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
        return h.hexdigest()

    def fields(self, draft_id: str, lang: str = "ko") -> tuple[dict, str]:
        path = self.draft_paths(draft_id).get(lang)
        if path is None:
            raise StoreError(f"{draft_id}에 {lang} 판이 없다")
        return frontmatter.parse(path.read_text(encoding="utf-8"))

    def status(self, draft_id: str) -> str:
        meta = self.meta(draft_id)
        if meta.get("published"):
            return "published"
        if meta.get("held"):
            return "held"
        h = self.content_hash(draft_id)
        decisions = self.decisions(draft_id)
        if decisions and decisions[-1]["hash"] == h:
            return "approved" if decisions[-1]["decision"] == "approved" else "rejected"
        requests = meta.get("approval_requests", [])
        if requests and requests[-1]["hash"] == h:
            return "awaiting_approval"
        if self._passed_quality(meta, h):
            return "ready"
        return "writing"

    @staticmethod
    def _passed_quality(meta: dict, h: str) -> bool:
        quality = meta.get("quality", [])
        return bool(quality) and quality[-1]["hash"] == h and quality[-1]["passed"]

    def summary(self, draft_id: str) -> dict:
        meta = self.meta(draft_id)
        try:
            fields, _ = self.fields(draft_id, "ko")
        except (StoreError, ValueError) as e:
            # 파일 하나가 깨져도 목록 전체가 실패하지 않게 한다
            fields = {"title": f"(읽을 수 없음: {e})"}
        decisions = self.decisions(draft_id)
        last_reject = next((d for d in reversed(decisions) if d["decision"] == "rejected"), None)
        return {
            "draft_id": draft_id,
            "status": self.status(draft_id),
            "title": fields.get("title"),
            "description": fields.get("description"),
            "series": meta.get("series"),
            "backlog_id": meta.get("backlog_id"),
            "langs": sorted(self.draft_paths(draft_id)),
            "hash": self.content_hash(draft_id),
            "created_at": meta["created_at"],
            "updated_at": meta["updated_at"],
            "last_quality": (meta.get("quality") or [None])[-1],
            "last_rejection": last_reject,
            "held": meta.get("held"),
            "published": meta.get("published"),
        }

    def list_drafts(self) -> list[dict]:
        if not self.config.drafts_dir.is_dir():
            return []
        ids = sorted(p.name for p in self.config.drafts_dir.iterdir() if p.is_dir() and DRAFT_ID_RE.match(p.name))
        return [self.summary(i) for i in ids]

    # ── 쓰기 (Huninn) ─────────────────────────────────────

    def create_draft(self, *, slug: str, series: str, ko: dict, en: Optional[dict] = None,
                     sources: Optional[list] = None, backlog_id: Optional[str] = None,
                     note: str = "초안 작성") -> str:
        if not SLUG_RE.match(slug or "") or len(slug) > 60:
            raise StoreError(f"슬러그는 소문자·숫자·하이픈으로 60자 이내여야 한다: {slug!r}")
        if series not in SERIES:
            raise StoreError(f"없는 시리즈다: {series!r} (가능: {', '.join(SERIES)})")
        draft_id = f"{self._now():%Y%m%d}-{slug}"
        with self._lock():
            d = self.config.drafts_dir / draft_id
            if d.exists():
                raise StoreError(f"같은 ID의 초안이 이미 있다: {draft_id}")
            d.mkdir(parents=True)
            self._write_langs(d, series=series, ko=ko, en=en, sources=sources)
            ts = self._ts()
            _write_json(d / "meta.json", {
                "draft_id": draft_id,
                "slug": slug,
                "series": series,
                "backlog_id": backlog_id,
                "created_at": ts,
                "updated_at": ts,
                "revisions": [{"at": ts, "note": note, "hash": self.content_hash(draft_id)}],
                "quality": [],
                "approval_requests": [],
                "held": None,
                "published": None,
            })
        return draft_id

    def update_draft(self, draft_id: str, *, note: str, ko: Optional[dict] = None,
                     en: Optional[dict] = None, sources: Optional[list] = None) -> None:
        if not (note or "").strip():
            raise StoreError("무엇을 왜 고쳤는지(note)가 필요하다")
        with self._lock():
            d = self._dir(draft_id)
            meta = self.meta(draft_id)
            if meta.get("published"):
                raise StoreError("이미 발행된 초안은 고칠 수 없다")
            if meta.get("held"):
                raise StoreError("보류된 초안은 고칠 수 없다. 운영자의 판단이 필요하다")
            merged = {}
            for lang, change in (("ko", ko), ("en", en)):
                current = None
                if (d / f"index.{lang}.md").exists():
                    fields, body = frontmatter.parse((d / f"index.{lang}.md").read_text(encoding="utf-8"))
                    current = {"title": fields.get("title"), "description": fields.get("description"),
                               "tags": fields.get("tags", []), "body": body}
                    if sources is None:
                        sources = fields.get("sources")
                merged[lang] = {**(current or {}), **(change or {})} if (current or change) else None
            self._write_langs(d, series=meta["series"], ko=merged["ko"], en=merged["en"], sources=sources)
            ts = self._ts()
            meta["updated_at"] = ts
            meta["revisions"].append({"at": ts, "note": note.strip(), "hash": self.content_hash(draft_id)})
            _write_json(d / "meta.json", meta)

    def _write_langs(self, d: Path, *, series: str, ko: Optional[dict], en: Optional[dict],
                     sources: Optional[list]) -> None:
        if not ko:
            raise StoreError("한국어판(ko)은 반드시 있어야 한다")
        for lang, part in (("ko", ko), ("en", en)):
            if part is None:
                continue
            missing = [k for k in ("title", "description", "body") if not str(part.get(k) or "").strip()]
            if missing:
                raise StoreError(f"{lang} 판에 빠진 항목: {', '.join(missing)}")
            fields = {"title": part["title"].strip(), "description": part["description"].strip(),
                      "series": [series], "tags": list(part.get("tags") or [])}
            if sources:
                fields["sources"] = sources
            _write_atomic(d / f"index.{lang}.md", frontmatter.render(fields, part["body"]))

    def record_quality(self, draft_id: str, passed: bool, problems: list[str]) -> dict:
        with self._lock():
            meta = self.meta(draft_id)
            record = {"at": self._ts(), "hash": self.content_hash(draft_id), "passed": passed, "problems": problems}
            meta["quality"].append(record)
            _write_json(self._dir(draft_id) / "meta.json", meta)
        return record

    def consecutive_quality_failures(self, draft_id: str) -> int:
        # 마지막 통과 이후 실패한 서로 다른 버전(해시) 수. 같은 내용을 다시 검사해도 늘지 않는다
        failed = set()
        for record in reversed(self.meta(draft_id).get("quality", [])):
            if record["passed"]:
                break
            failed.add(record["hash"])
        return len(failed)

    def record_approval_request(self, draft_id: str) -> dict:
        with self._lock():
            if self.status(draft_id) != "ready":
                raise StoreError(f"품질 검사를 통과한 지금 버전만 승인을 요청할 수 있다 (지금: {self.status(draft_id)})")
            waiting = [s["draft_id"] for s in self.list_drafts() if s["status"] == "awaiting_approval"]
            if len(waiting) >= self.config.max_pending_approval:
                raise StoreError(f"이미 승인을 기다리는 초안이 있다: {', '.join(waiting)}")
            meta = self.meta(draft_id)
            record = {"at": self._ts(), "hash": self.content_hash(draft_id)}
            meta["approval_requests"].append(record)
            _write_json(self._dir(draft_id) / "meta.json", meta)
        return record

    def mark_published(self, draft_id: str, record: dict) -> None:
        with self._lock():
            meta = self.meta(draft_id)
            meta["published"] = record
            _write_json(self._dir(draft_id) / "meta.json", meta)

    def passed_quality(self, draft_id: str) -> bool:
        return self._passed_quality(self.meta(draft_id), self.content_hash(draft_id))

    def mark_held(self, draft_id: str, reason: str) -> None:
        with self._lock():
            meta = self.meta(draft_id)
            meta["held"] = {"at": self._ts(), "reason": reason}
            _write_json(self._dir(draft_id) / "meta.json", meta)

    # ── 쓰기 (사람: review 명령) ──────────────────────────

    def record_decision(self, draft_id: str, decision: str, reason: Optional[str] = None,
                        by: str = "operator") -> dict:
        if decision not in ("approved", "rejected"):
            raise StoreError(f"결정은 approved 또는 rejected다: {decision!r}")
        with self._lock():
            status = self.status(draft_id)
            h = self.content_hash(draft_id)
            if decision == "approved":
                if status != "awaiting_approval":
                    raise StoreError(f"승인 대기 중인 초안만 승인할 수 있다 (지금: {STATUS_LABELS[status]})")
                if not self._passed_quality(self.meta(draft_id), h):
                    raise StoreError("품질 검사를 통과한 버전과 지금 내용이 다르다")
            else:
                if status not in ("awaiting_approval", "approved"):
                    raise StoreError(f"승인 대기 또는 승인된 초안만 반려할 수 있다 (지금: {STATUS_LABELS[status]})")
                if not (reason or "").strip():
                    raise StoreError("반려 사유가 필요하다. Huninn은 이 사유를 보고 고친다")
            record = {"at": self._ts(), "decision": decision, "hash": h, "by": by}
            if decision == "rejected":
                record["reason"] = reason.strip()
            data = _read_json(self._approval_path(draft_id), {"draft_id": draft_id, "decisions": []})
            data["decisions"].append(record)
            _write_json(self._approval_path(draft_id), data)
        return record
