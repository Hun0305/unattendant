import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import review
from blogops.config import Config
from blogops.store import Store

KO = {"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": "본문."}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = review.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BLOGOPS_ROOT": self.tmp.name})
        self.env.start()
        self.store = Store(Config.from_env())
        self.draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def request(self):
        self.store.record_quality(self.draft_id, True, [])
        self.store.record_approval_request(self.draft_id)

    def test_list_and_show(self):
        code, out, _ = run("list")
        self.assertEqual(code, 0)
        self.assertIn(self.draft_id, out)
        self.assertIn("작성 중", out)
        code, out, _ = run("show", self.draft_id, "--body")
        self.assertEqual(code, 0)
        self.assertIn("index.ko.md", out)
        self.assertIn("본문.", out)

    def test_approve_logs_decision(self):
        self.request()
        code, out, _ = run("approve", self.draft_id)
        self.assertEqual(code, 0)
        self.assertIn("승인했다", out)
        self.assertEqual(self.store.status(self.draft_id), "approved")
        logs = list((Path(self.tmp.name) / "logs").glob("*.jsonl"))
        records = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[-1]["event"], "approval_decision")
        self.assertEqual(records[-1]["actor"], "operator")

    def test_approve_wrong_state_fails(self):
        code, _, err = run("approve", self.draft_id)
        self.assertEqual(code, 1)
        self.assertIn("승인 대기 중인 초안만", err)

    def test_reject_needs_reason(self):
        self.request()
        code, _, err = run("reject", self.draft_id, "   ")
        self.assertEqual(code, 1)
        self.assertIn("반려 사유", err)
        with self.assertRaises(SystemExit):  # 사유 인자 자체가 없으면 argparse가 막는다
            with contextlib.redirect_stderr(io.StringIO()):
                review.main(["reject", self.draft_id])
        code, out, _ = run("reject", self.draft_id, "출처가 없다")
        self.assertEqual(code, 0)
        self.assertEqual(self.store.status(self.draft_id), "rejected")

    def test_unknown_draft(self):
        code, _, err = run("show", "20990101-nope")
        self.assertEqual(code, 1)
        self.assertIn("없는 초안", err)


if __name__ == "__main__":
    unittest.main()
