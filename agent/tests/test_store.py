import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from blogops import frontmatter
from blogops.config import KST, Config
from blogops.store import Store, StoreError

KO = {"title": "이름 짓기", "description": "unattendant가 되기까지", "tags": ["meta"], "body": "본문 첫 문단.\n\n둘째 문단."}
EN = {"title": "Naming", "description": "How it became unattendant", "tags": ["meta"], "body": "First paragraph."}


class Clock:
    def __init__(self):
        self.t = datetime(2026, 10, 8, 14, 0, tzinfo=KST)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


def make_store(tmp):
    return Store(Config(root=Path(tmp), clock=Clock()))


def ready(store, draft_id):
    store.record_quality(draft_id, True, [])


class FrontmatterTest(unittest.TestCase):
    def test_round_trip(self):
        fields = {"title": '따옴표 "와" 역슬래시 \\', "description": "요약", "series": ["ops-log"],
                  "tags": ["a", "나"], "sources": [{"title": "문서", "url": "https://example.com/a?b=1"}]}
        text = frontmatter.render(fields, "본문\n")
        parsed, body = frontmatter.parse(text)
        self.assertEqual(parsed, fields)
        self.assertEqual(body, "본문\n")

    def test_missing_front_matter(self):
        with self.assertRaises(ValueError):
            frontmatter.parse("본문만 있다\n")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = make_store(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO, backlog_id="naming")
        self.assertEqual(draft_id, "20261008-naming")
        self.assertEqual(self.store.status(draft_id), "writing")
        fields, body = self.store.fields(draft_id)
        self.assertEqual(fields["series"], ["ops-log"])
        self.assertNotIn("date", fields)
        self.assertNotIn("author", fields)
        self.assertEqual(self.store.meta(draft_id)["backlog_id"], "naming")

    def test_invalid_input(self):
        for slug in ("Naming", "a_b", "-a", "a--b", "", "x" * 61):
            with self.assertRaises(StoreError, msg=slug):
                self.store.create_draft(slug=slug, series="ops-log", ko=KO)
        with self.assertRaises(StoreError):
            self.store.create_draft(slug="ok", series="nope", ko=KO)
        with self.assertRaises(StoreError):
            self.store.create_draft(slug="ok", series="ops-log", ko={**KO, "body": "  "})
        with self.assertRaises(StoreError):
            self.store.status("../../etc")

    def test_duplicate(self):
        self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        with self.assertRaises(StoreError):
            self.store.create_draft(slug="naming", series="ops-log", ko=KO)

    def test_hash_changes_with_content_and_files(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        h1 = self.store.content_hash(draft_id)
        self.assertEqual(h1, self.store.content_hash(draft_id))
        self.store.update_draft(draft_id, note="영어판 추가", en=EN)
        h2 = self.store.content_hash(draft_id)
        self.assertNotEqual(h1, h2)
        self.store.update_draft(draft_id, note="한 글자", ko={"body": KO["body"] + "!"})
        self.assertNotEqual(h2, self.store.content_hash(draft_id))

    def test_approval_flow(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        with self.assertRaises(StoreError):  # 품질 통과 전에는 승인 요청 불가
            self.store.record_approval_request(draft_id)
        ready(self.store, draft_id)
        self.assertEqual(self.store.status(draft_id), "ready")
        with self.assertRaises(StoreError):  # 요청 전에는 승인 불가
            self.store.record_decision(draft_id, "approved")
        self.store.record_approval_request(draft_id)
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        self.store.record_decision(draft_id, "approved")
        self.assertEqual(self.store.status(draft_id), "approved")
        with self.assertRaises(StoreError):  # 이미 승인된 초안을 또 승인할 수 없다
            self.store.record_decision(draft_id, "approved")

    def test_edit_after_approval_releases_it(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        self.store.update_draft(draft_id, note="다듬기", ko={"body": KO["body"] + " 덧붙임"})
        self.assertEqual(self.store.status(draft_id), "writing")
        self.assertEqual(len(self.store.decisions(draft_id)), 1)

    def test_file_edited_outside_store_releases_approval(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        path = self.store.draft_paths(draft_id)["ko"]
        path.write_text(path.read_text(encoding="utf-8").replace("둘째", "셋째"), encoding="utf-8")
        self.assertEqual(self.store.status(draft_id), "writing")

    def test_reject_then_revise(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        for blank in (None, "", "   "):
            with self.assertRaises(StoreError):
                self.store.record_decision(draft_id, "rejected", reason=blank)
        self.store.record_decision(draft_id, "rejected", reason="고른 이유가 빠졌다")
        self.assertEqual(self.store.status(draft_id), "rejected")
        self.assertEqual(self.store.summary(draft_id)["last_rejection"]["reason"], "고른 이유가 빠졌다")
        self.store.update_draft(draft_id, note="반려 사유 반영: 고른 이유 추가", ko={"body": KO["body"] + "\n\n고른 이유."})
        self.assertEqual(self.store.status(draft_id), "writing")
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        self.assertEqual(self.store.status(draft_id), "approved")
        self.assertEqual([d["decision"] for d in self.store.decisions(draft_id)], ["rejected", "approved"])

    def test_reject_after_approval(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        self.store.record_decision(draft_id, "rejected", reason="다시 보니 숫자 출처가 없다")
        self.assertEqual(self.store.status(draft_id), "rejected")

    def test_failed_quality_after_request_blocks_approval(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        ready(self.store, draft_id)
        self.store.record_approval_request(draft_id)
        self.store.record_quality(draft_id, False, ["규칙이 바뀌어 실패"])
        with self.assertRaises(StoreError):
            self.store.record_decision(draft_id, "approved")

    def test_pending_limit(self):
        a = self.store.create_draft(slug="a", series="ops-log", ko=KO)
        b = self.store.create_draft(slug="b", series="ops-log", ko=KO)
        ready(self.store, a)
        ready(self.store, b)
        self.store.record_approval_request(a)
        with self.assertRaises(StoreError):
            self.store.record_approval_request(b)
        self.store.record_decision(a, "approved")
        self.store.record_approval_request(b)  # a가 더는 대기 중이 아니다
        self.assertEqual(self.store.status(b), "awaiting_approval")

    def test_held(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        for _ in range(3):
            self.store.record_quality(draft_id, False, ["출처 없음"])
        self.assertEqual(self.store.consecutive_quality_failures(draft_id), 3)
        self.store.mark_held(draft_id, "품질 검사 3번 실패")
        self.assertEqual(self.store.status(draft_id), "held")
        with self.assertRaises(StoreError):
            self.store.update_draft(draft_id, note="고침", ko={"body": "새 본문"})

    def test_update_keeps_other_fields(self):
        sources = [{"title": "pre-commit.md", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/pre-commit.md"}]
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO, en=EN, sources=sources)
        self.store.update_draft(draft_id, note="제목만", ko={"title": "새 제목"})
        ko_fields, ko_body = self.store.fields(draft_id, "ko")
        en_fields, _ = self.store.fields(draft_id, "en")
        self.assertEqual(ko_fields["title"], "새 제목")
        self.assertEqual(ko_fields["description"], KO["description"])
        self.assertEqual(ko_body.strip(), KO["body"])
        self.assertEqual(ko_fields["sources"], sources)
        self.assertEqual(en_fields["title"], EN["title"])
        with self.assertRaises(StoreError):
            self.store.update_draft(draft_id, note="  ", ko={"title": "x"})

    def test_list_survives_broken_file(self):
        good = self.store.create_draft(slug="good", series="ops-log", ko=KO)
        bad = self.store.create_draft(slug="bad", series="ops-log", ko=KO)
        self.store.draft_paths(bad)["ko"].write_text("front matter 없음", encoding="utf-8")
        listed = {d["draft_id"]: d for d in self.store.list_drafts()}
        self.assertEqual(listed[good]["title"], KO["title"])
        self.assertIn("읽을 수 없음", listed[bad]["title"])


if __name__ == "__main__":
    unittest.main()
