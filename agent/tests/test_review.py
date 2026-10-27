import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import backlog, review
from blogops.config import Config
from blogops.store import Store

KO = {"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": "본문."}
BACKLOG = {"updated": "2026-10-07", "items": [
    {"id": "naming", "title": "이름 짓기", "series": "ops-log", "status": "idea", "sources": [], "notes": "",
     "added": "2026-10-07", "added_by": "operator"}]}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = review.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # 매장의 진짜 비밀값을 읽지 않게 없는 파일을 가리킨다 (디스코드로 보내는 길이 막힌다)
        self.env = mock.patch.dict(os.environ, {"BLOGOPS_ROOT": self.tmp.name,
                                                "BLOGOPS_ENV_FILE": str(Path(self.tmp.name) / "none.env")})
        self.env.start()
        # 기본은 즉시 실행 유닛이 없는 환경. 실제 systemctl을 부르지 않는다
        self.watch = mock.patch("blogops.ondemand.watcher_active", return_value=False)
        self.watcher = self.watch.start()
        self.store = Store(Config.from_env())
        self.draft_id = self.store.create_draft(slug="naming", series="ops-log", ko=KO, backlog_id="naming")
        (Path(self.tmp.name) / "state" / "backlog.json").write_text(json.dumps(BACKLOG, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.watch.stop()
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

    def test_approve_records_cli_as_source(self):
        self.request()
        run("approve", self.draft_id)
        self.assertEqual(self.store.decisions(self.draft_id)[-1]["via"], "cli")
        logs = list((Path(self.tmp.name) / "logs").glob("*.jsonl"))
        records = [json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[-1]["via"], "cli")

    def test_reject_drop_holds_and_blocks_backlog(self):
        self.request()
        code, out, err = run("reject", self.draft_id, "이 주제는 그만", "--drop")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("접었다", out)
        self.assertEqual(self.store.status(self.draft_id), "held")
        self.assertEqual(backlog.items(Config.from_env(), "blocked")[0]["id"], "naming")

    def test_reject_tells_what_happens_next(self):
        self.request()
        _, out, _ = run("reject", self.draft_id, "출처가 없다")
        self.assertIn("다음 14:00 사이클에서 Huninn이 사유를 읽고 고친", out)  # 즉시 실행 유닛이 없으면 거짓말하지 않는다
        self.assertFalse(Config.from_env().cycle_request_path.exists())

    def test_reject_and_drop_run_the_cycle_right_away_when_the_unit_is_watching(self):
        self.watcher.return_value = True
        self.request()
        _, out, _ = run("reject", self.draft_id, "출처가 없다")
        self.assertIn("사이클을 바로 돌린다", out)
        self.assertIn("임시 실행 1/5회", out)
        self.assertTrue(Config.from_env().cycle_request_path.exists())

    def test_approve_does_not_run_the_cycle(self):
        self.watcher.return_value = True
        self.request()
        _, out, _ = run("approve", self.draft_id)
        self.assertIn("다음 사이클(매일 14:00)에서 발행된다", out)
        self.assertFalse(Config.from_env().cycle_request_path.exists())

    def test_reject_without_drop_keeps_backlog(self):
        self.request()
        run("reject", self.draft_id, "출처가 없다")
        self.assertEqual(backlog.items(Config.from_env(), "blocked"), [])

    def test_preview_command_and_show(self):
        code, _, err = run("preview", self.draft_id)  # 아직 승인 대기가 아니다
        self.assertEqual(code, 1)
        self.assertIn("승인 대기", err)
        self.request()
        code, out, _ = run("show", self.draft_id)
        self.assertNotIn("미리보기", out)  # 아직 만들지 않았다

    def test_preview_command_builds_and_show_lists_url(self):
        # 실제 Hugo 빌드는 test_preview.py가 본다. 여기서는 명령이 연결되는지만 본다
        self.request()
        fake = {"draft_id": self.draft_id, "token": "t" * 40, "hash": "h", "reused": False,
                "urls": {"ko": "https://preview.example/ttt/posts/naming/"}}
        with mock.patch("blogops.review.preview.ensure", return_value=fake):
            code, out, _ = run("preview", self.draft_id)
        self.assertEqual(code, 0)
        self.assertIn("https://preview.example/ttt/posts/naming/", out)
        with mock.patch("blogops.review.preview.current", return_value=fake):
            _, out, _ = run("show", self.draft_id)
        self.assertIn("미리보기 ko https://preview.example/ttt/posts/naming/", out)

    def test_unknown_draft(self):
        code, _, err = run("show", "20990101-nope")
        self.assertEqual(code, 1)
        self.assertIn("없는 초안", err)


if __name__ == "__main__":
    unittest.main()
