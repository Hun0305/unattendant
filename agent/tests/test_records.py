import os
import subprocess
import tempfile
import unittest
from datetime import date, timedelta

from blogops import records
from blogops.records import RecordError
from helpers import make_env


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, _ = make_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list(self):
        listed = {r["path"]: r for r in records.list_records(self.config)}
        self.assertEqual(set(listed), {"docs/pre-commit.md", "ops/README.md", "site/README.md"})
        self.assertEqual(listed["docs/pre-commit.md"]["title"], "비밀키 스캐너")

    def test_read_in_chunks(self):
        first = records.read_record(self.config, "docs/pre-commit.md")
        self.assertEqual(len(first["text"]), records.READ_LIMIT)
        self.assertEqual(first["next_offset"], records.READ_LIMIT)
        rest = records.read_record(self.config, "docs/pre-commit.md", offset=first["next_offset"] * 2)
        self.assertIsNone(rest["next_offset"])
        self.assertEqual(records.read_record(self.config, "site/README.md")["text"], "# unattendant.dev\n")

    def test_blocked_paths(self):
        for path in (".env", "logs/x.jsonl", "CLAUDE.md", "state/drafts/x/index.ko.md", "../ops/.env",
                     "/etc/passwd", "docs/../.env", "", "ops/gitleaks.toml", "docs/없는파일.md"):
            with self.assertRaises(RecordError, msg=path):
                records.read_record(self.config, path)

    def test_symlink_escape(self):
        os.symlink(self.config.root / ".env", self.config.root / "docs" / "leak.md")
        with self.assertRaises(RecordError):
            records.read_record(self.config, "docs/leak.md")
        self.assertNotIn("docs/leak.md", [r["path"] for r in records.list_records(self.config)])

    def test_git_log(self):
        git = ["git", "-C", str(self.config.root), "-c", "core.hooksPath=/dev/null",
               "-c", "user.name=Hun0305", "-c", "user.email=t@example.invalid"]
        subprocess.run(git[:3] + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "docs"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "docs: 첫 커밋\n\n본문 줄\n\nCo-Authored-By: X <x@example.invalid>"], check=True)
        log = records.git_log(self.config, "ops")
        self.assertEqual(log[0]["subject"], "docs: 첫 커밋")
        self.assertEqual(log[0]["body"], "본문 줄")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(records.git_log(self.config, "ops", since=tomorrow), [])
        self.assertEqual(len(records.git_log(self.config, "ops", since=yesterday)), 1)
        for kwargs in ({"repo": "other"}, {"since": "어제"}):
            with self.assertRaises(RecordError):
                records.git_log(self.config, **kwargs)

    def test_site_posts_reads_loose_front_matter(self):
        posts = records.site_posts(self.config)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["slug"], "starting-unattendant")
        self.assertEqual(posts[0]["author"], "human")
        self.assertEqual(posts[0]["date"], "2026-10-06T20:34:00+09:00")
        self.assertEqual(posts[0]["series"], ["ops-log"])


if __name__ == "__main__":
    unittest.main()
