import os
import tempfile
import time
import unittest
from unittest import mock

from blogops import preview
from blogops.config import Config
from blogops.preview import PreviewError
from helpers import good_body, make_env

PAGE = ('<!doctype html><html><head><meta charset="utf-8"><title>{{ .Title }}</title></head>'
        '<body><a id="self" href="{{ .RelPermalink }}">self</a><h1>{{ .Title }}</h1>{{ .Content }}</body></html>\n')
KO = {"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": ""}
EN = {"title": "Naming", "description": "summary", "tags": ["meta"], "body": "English body. " * 40}


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # 미리보기는 벽시계 기준으로 빌드하므로 실제 시계를 쓰는 환경을 쓴다
        self.config, self.store = make_env(self.tmp.name, real_clock=True)
        (self.config.site_dir / "layouts" / "page.html").write_text(PAGE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def awaiting(self, slug="naming", en=False, body=None):
        ko = {**KO, "body": body or good_body()}
        draft_id = self.store.create_draft(slug=slug, series="ops-log", ko=ko, en=EN if en else None)
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        return draft_id

    def test_build_marks_draft_page_only(self):
        draft_id = self.awaiting(en=True)
        result = preview.ensure(self.config, self.store, draft_id)
        self.assertFalse(result["reused"])
        token = result["token"]
        self.assertRegex(token, r"^[0-9a-f]{40}$")
        self.assertEqual(result["urls"], {
            "ko": f"https://preview.unattendant.dev/{token}/posts/naming/",
            "en": f"https://preview.unattendant.dev/{token}/en/posts/naming/"})
        root = self.config.previews_dir / token
        ko_page = (root / "posts" / "naming" / "index.html").read_text(encoding="utf-8")
        self.assertIn("이름 짓기", ko_page)
        self.assertIn("미승인 초안 미리보기", ko_page)
        self.assertIn(result["hash"][:12], ko_page)
        # 기준 주소가 미리보기 호스트와 토큰으로 바뀌어, 사이트 안의 링크가 토큰 폴더 안에서 이어진다
        self.assertIn(f'href="/{token}/posts/naming/"', ko_page)
        en_page = (root / "en" / "posts" / "naming" / "index.html").read_text(encoding="utf-8")
        self.assertIn("미승인 초안 미리보기", en_page)
        # 사이트의 다른 글에는 띠가 없고, 초안은 이 폴더 밖(공개 사이트)에 새지 않는다
        other = (root / "posts" / "starting-unattendant" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("미승인 초안", other)
        self.assertFalse((self.config.site_dir / "public" / "posts" / "naming").exists())
        self.assertFalse(any(p.name.startswith(preview.BUILD_PREFIX) for p in self.config.previews_dir.iterdir()))

    def test_reuse_then_new_token_when_content_changes(self):
        draft_id = self.awaiting()
        first = preview.ensure(self.config, self.store, draft_id)
        again = preview.ensure(self.config, self.store, draft_id)
        self.assertTrue(again["reused"])
        self.assertEqual(again["token"], first["token"])
        self.assertEqual(preview.current(self.config, self.store, draft_id)["token"], first["token"])
        # 내용이 바뀌면 승인 대기가 풀리고, 다시 요청한 버전은 새 토큰을 받는다. 옛 폴더는 지워진다
        self.store.update_draft(draft_id, note="고침", ko={"body": good_body("덧붙임.")})
        self.assertIsNone(preview.current(self.config, self.store, draft_id))
        with self.assertRaises(PreviewError):
            preview.ensure(self.config, self.store, draft_id)  # 승인 대기가 아니다
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        second = preview.ensure(self.config, self.store, draft_id)
        self.assertNotEqual(second["token"], first["token"])
        self.assertFalse((self.config.previews_dir / first["token"]).exists())
        self.assertTrue((self.config.previews_dir / second["token"]).is_dir())

    def test_only_awaiting_drafts(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko={**KO, "body": good_body()})
        with self.assertRaises(PreviewError) as cm:
            preview.ensure(self.config, self.store, draft_id)
        self.assertIn("승인 대기", str(cm.exception))
        self.assertFalse(self.config.previews_dir.exists())

    def test_assets_are_copied_so_figures_resolve(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko={**KO, "body": good_body()})
        (self.config.drafts_dir / draft_id / "pic.png").write_bytes(b"\x89PNG fake")
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        token = preview.ensure(self.config, self.store, draft_id)["token"]
        self.assertTrue((self.config.previews_dir / token / "posts" / "naming" / "pic.png").exists())

    def test_cleanup(self):
        keep = preview.ensure(self.config, self.store, self.awaiting())["token"]
        previews = self.config.previews_dir
        (previews / ("f" * 40)).mkdir()  # 어느 초안의 것도 아니다
        (previews / ("f" * 40) / "index.html").write_text("x")
        fresh, stale = previews / f"{preview.BUILD_PREFIX}fresh", previews / f"{preview.BUILD_PREFIX}stale"
        fresh.mkdir()
        stale.mkdir()
        old = time.time() - preview.BUILD_STALE_SECONDS - 60
        os.utime(stale, (old, old))
        (previews / "notes.txt").write_text("폴더가 아니면 건드리지 않는다")
        removed = preview.cleanup(self.config, self.store)
        self.assertEqual(sorted(removed), sorted(["f" * 40, f"{preview.BUILD_PREFIX}stale"]))
        self.assertTrue((previews / keep).is_dir())
        self.assertTrue(fresh.is_dir())  # 지금 만드는 중일 수 있다
        self.assertTrue((previews / "notes.txt").exists())

    def test_cleanup_after_decision_removes_preview(self):
        draft_id = self.awaiting()
        token = preview.ensure(self.config, self.store, draft_id)["token"]
        self.store.record_decision(draft_id, "approved")
        self.assertEqual(preview.cleanup(self.config, self.store), [token])
        self.assertEqual(preview.cleanup(self.config, self.store), [])

    def test_cleanup_without_directory(self):
        self.assertEqual(preview.cleanup(self.config, self.store), [])

    def test_failed_build_leaves_nothing(self):
        draft_id = self.awaiting()
        (self.config.site_dir / "layouts" / "page.html").write_text("{{ .Nope.Nope }}", encoding="utf-8")
        with self.assertRaises(PreviewError) as cm:
            preview.ensure(self.config, self.store, draft_id)
        self.assertIn("빌드가 실패", str(cm.exception))
        self.assertEqual(list(self.config.previews_dir.iterdir()), [])
        self.assertIsNone(self.store.preview_record(draft_id))

    def test_template_without_body_tag_still_works(self):
        (self.config.site_dir / "layouts" / "page.html").write_text("<h1>{{ .Title }}</h1>{{ .Content }}\n", encoding="utf-8")
        result = preview.ensure(self.config, self.store, self.awaiting())
        page = (self.config.previews_dir / result["token"] / "posts" / "naming" / "index.html").read_text(encoding="utf-8")
        self.assertIn("이름 짓기", page)
        self.assertNotIn("미승인 초안", page)  # 띠만 빠진다

    def test_base_url_from_env(self):
        with mock.patch.dict(os.environ, {"BLOGOPS_ROOT": self.tmp.name,
                                          "BLOGOPS_PREVIEW_BASE_URL": "https://p.example.org/"}):
            self.assertEqual(Config.from_env().preview_base_url, "https://p.example.org")
        with mock.patch.dict(os.environ, {"BLOGOPS_ROOT": self.tmp.name}):
            os.environ.pop("BLOGOPS_PREVIEW_BASE_URL", None)
            self.assertEqual(Config.from_env().preview_base_url, "https://preview.unattendant.dev")


if __name__ == "__main__":
    unittest.main()
