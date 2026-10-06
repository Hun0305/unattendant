import subprocess
import tempfile
import unittest
from pathlib import Path

from blogops import backlog, frontmatter, publish
from blogops.config import find_tool
from blogops.publish import PublishError
from helpers import git, good_body, make_publish_env

KO = {"title": '이름 짓기: "unattendant"가 되기까지', "description": "탈락한 후보와 고른 이유",
      "tags": ["meta"], "body": good_body()}


def ok(url, title):
    return True


@unittest.skipUnless(find_tool("hugo"), "hugo가 있어야 한다")
class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store, self.origin = make_publish_env(self.tmp.name)
        self.site = self.config.site_dir

    def tearDown(self):
        self.tmp.cleanup()

    def approved(self, slug="naming", backlog_id="naming", ko=KO):
        draft_id = self.store.create_draft(slug=slug, series="ops-log", ko=ko, backlog_id=backlog_id)
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        return draft_id

    def head(self, repo):
        return git(repo, "log", "-1", "--format=%an|%ae|%s").stdout.strip()

    def test_publish(self):
        draft_id = self.approved()
        result = publish.publish_post(self.config, self.store, draft_id, verify=ok)
        self.assertTrue(result["pushed"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["url"], "https://example.org/posts/naming/")
        # 사이트 원본에 date가 들어간 글, 실제 public/ 빌드
        fields, _ = frontmatter.parse((self.site / "content/posts/naming/index.ko.md").read_text(encoding="utf-8"))
        self.assertEqual(fields["date"], result["at"])
        self.assertTrue((self.site / "public/posts/naming/index.html").exists())
        # 커밋은 작성자 Huninn, origin에도 올라갔다
        self.assertEqual(self.head(self.site), f'Huninn|huninn@unattendant.dev|content(ai): {KO["title"]}')
        self.assertEqual(self.head(self.origin), self.head(self.site))
        body = git(self.site, "log", "-1", "--format=%b").stdout
        self.assertIn(f"초안 {draft_id}", body)
        self.assertIn("백로그 글감 naming", body)
        # 상태와 백로그
        self.assertEqual(self.store.status(draft_id), "published")
        self.assertEqual(backlog.items(self.config, "published")[0]["id"], "naming")

    def test_only_approved_version(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)
        with self.assertRaises(PublishError):  # 작성 중
            publish.publish_post(self.config, self.store, draft_id, verify=ok)
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        with self.assertRaises(PublishError):  # 승인 대기
            publish.publish_post(self.config, self.store, draft_id, verify=ok)
        self.store.record_decision(draft_id, "approved")
        path = self.store.draft_paths(draft_id)["ko"]
        path.write_text(path.read_text(encoding="utf-8") + "\n승인 뒤 덧붙인 문장\n", encoding="utf-8")
        with self.assertRaises(PublishError):  # 승인 뒤 바뀜
            publish.publish_post(self.config, self.store, draft_id, verify=ok)
        self.assertFalse((self.site / "content/posts/naming").exists())

    def test_one_per_day(self):
        a = self.approved(slug="first", backlog_id=None, ko={**KO, "title": "첫째 글"})
        b = self.approved(slug="second", backlog_id=None, ko={**KO, "title": "둘째 글"})
        publish.publish_post(self.config, self.store, a, verify=ok)
        with self.assertRaisesRegex(PublishError, "오늘은 이미"):
            publish.publish_post(self.config, self.store, b, verify=ok)

    def test_build_failure_rolls_back(self):
        before = self.head(self.site)
        draft_id = self.approved(ko={**KO, "body": good_body("{{< 없는단축코드 >}}")})
        with self.assertRaises(PublishError):
            publish.publish_post(self.config, self.store, draft_id, verify=ok)
        self.assertFalse((self.site / "content/posts/naming").exists())
        self.assertEqual(self.head(self.site), before)
        self.assertEqual(git(self.site, "status", "--porcelain").stdout, "")
        self.assertTrue((self.site / "public/posts/starting-unattendant/index.html").exists())  # 기존 글은 그대로
        self.assertEqual(self.store.status(draft_id), "approved")  # 고쳐서 다시 할 수 있다

    def test_push_conflict_rebases(self):
        other = Path(self.tmp.name) / "other"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(other)], check=True)
        (other / "README.md").write_text("사람이 먼저 push한 변경\n", encoding="utf-8")
        git(other, "add", "README.md")
        git(other, "commit", "-q", "-m", "사람 커밋")
        git(other, "push", "-q", "origin", "main")
        result = publish.publish_post(self.config, self.store, self.approved(), verify=ok)
        self.assertTrue(result["pushed"])
        subjects = git(self.origin, "log", "--format=%s", "-3").stdout.splitlines()
        self.assertEqual(subjects[:2], [f'content(ai): {KO["title"]}', "사람 커밋"])

    def test_push_failure_and_unverified(self):
        git(self.site, "remote", "set-url", "origin", str(Path(self.tmp.name) / "없는-저장소.git"))
        result = publish.publish_post(self.config, self.store, self.approved(), verify=lambda url, title: False)
        self.assertFalse(result["pushed"])
        self.assertFalse(result["verified"])
        self.assertEqual(len(result["warnings"]), 2)
        self.assertEqual(self.store.status(result["draft_id"]), "published")  # 글은 이미 사이트에 올라갔다


class BacklogTest(unittest.TestCase):
    def setUp(self):
        from helpers import make_env
        self.tmp = tempfile.TemporaryDirectory()
        self.config, _ = make_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_and_add(self):
        backlog.set_status(self.config, "naming", "drafting")
        self.assertEqual(backlog.items(self.config, "drafting")[0]["id"], "naming")
        for args in (("naming", "unknown"), ("nope", "idea"), ("naming", "blocked")):
            with self.assertRaises(backlog.BacklogError, msg=args):
                backlog.set_status(self.config, *args)
        backlog.set_status(self.config, "naming", "dropped", note="이미 첫 글에서 다뤘다")
        self.assertIn("이미 첫 글에서 다뤘다", backlog.items(self.config, "dropped")[0]["notes"])
        item = backlog.add_item(self.config, item_id="rss-fix", title="RSS에 소개 페이지가 섞였던 일", series="ops-log")
        self.assertEqual(item["added_by"], "huninn")
        for kwargs in ({"item_id": "rss-fix"}, {"item_id": "Bad_ID"}, {"item_id": "x", "series": "nope"}):
            with self.assertRaises(backlog.BacklogError, msg=kwargs):
                backlog.add_item(self.config, **{"title": "t", "series": "ops-log", **kwargs})


if __name__ == "__main__":
    unittest.main()
