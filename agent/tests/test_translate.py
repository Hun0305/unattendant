import subprocess
import tempfile
import unittest

from blogops import frontmatter, translate
from blogops.config import find_tool
from blogops.publish import PublishError
from helpers import git, good_body, make_publish_env

SRC = {"title": "pre-commit.md", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/pre-commit.md"}
KO = {"title": "이름 짓기", "description": "탈락한 후보와 고른 이유", "tags": ["meta"],
      "body": good_body("후보 3개를 놓고 골랐다."), "sources": [SRC]}
EN_BODY = "This blog runs on a single Raspberry Pi. Huninn handles everything from picking topics to publishing. " * 8


def ok(url, title):
    return True


def no_scan(config, paths):
    return []


@unittest.skipUnless(find_tool("hugo"), "hugo가 있어야 한다")
class TranslateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store, self.origin = make_publish_env(self.tmp.name)
        self.site = self.config.site_dir
        from blogops import publish
        draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO, sources=[SRC])
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "approved")
        publish.publish_post(self.config, self.store, draft_id, verify=ok)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, **kw):
        args = dict(title="Naming the blog", description="Which names lost and why", tags=["meta"],
                    body=EN_BODY, verify=ok, scan=no_scan)
        return translate.add_english(self.config, "naming", **{**args, **kw})

    def test_read_post(self):
        post = translate.read_post(self.config, "naming")
        self.assertEqual(post["title"], KO["title"])
        self.assertFalse(post["has_en"])
        self.assertEqual(post["sources"], [SRC])

    def test_add_english(self):
        result = self.add()
        self.assertTrue(result["pushed"] and result["verified"])
        self.assertEqual(result["url"], "https://example.org/en/posts/naming/")
        ko, _ = frontmatter.parse((self.site / "content/posts/naming/index.ko.md").read_text(encoding="utf-8"))
        en, body = frontmatter.parse((self.site / "content/posts/naming/index.en.md").read_text(encoding="utf-8"))
        self.assertEqual((en["date"], en["series"], en["sources"]), (ko["date"], ko["series"], ko["sources"]))
        self.assertTrue((self.site / "public/en/posts/naming/index.html").exists())
        self.assertEqual(git(self.site, "log", "-1", "--format=%an|%s").stdout.strip(),
                         "Huninn|content(ai): Naming the blog (영어판)")
        self.assertEqual(git(self.origin, "log", "-1", "--format=%s").stdout.strip(),
                         "content(ai): Naming the blog (영어판)")
        self.assertTrue(translate.read_post(self.config, "naming")["has_en"])

    def test_refuses_twice(self):
        self.add()
        with self.assertRaisesRegex(PublishError, "이미 있다"):
            self.add()

    def test_refuses_human_post(self):
        with self.assertRaisesRegex(PublishError, "운영자가 쓴 글"):
            translate.add_english(self.config, "starting-unattendant", title="t", description="d", tags=["a"],
                                  body=EN_BODY, verify=ok, scan=no_scan)

    def test_quality_problems_leave_no_file(self):
        for kw, text in ((dict(body="Too short."), "짧다"),
                         (dict(body="## ok\n\n# Title\n\n" + EN_BODY), "h1"),
                         (dict(body=EN_BODY + " Mail me at someone@example.com."), "이메일"),
                         (dict(body=EN_BODY + " See [this](/en/posts/no-such-post/)."), "링크한 글이 없다"),
                         (dict(tags=[]), "tags")):
            with self.assertRaisesRegex(PublishError, text):
                self.add(**kw)
        self.assertFalse((self.site / "content/posts/naming/index.en.md").exists())
        self.assertEqual(git(self.site, "status", "--porcelain").stdout.strip(), "")

    def test_bad_slug(self):
        with self.assertRaises(PublishError):
            translate.read_post(self.config, "../x")


if __name__ == "__main__":
    unittest.main()
