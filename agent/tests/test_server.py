"""MCP 서버 툴. mcp 패키지가 있어야 돈다: agent/.venv/bin/python -m unittest discover -s tests"""
import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

try:
    from blogops import server
except ImportError as e:  # 시스템 python3에는 mcp가 없다
    raise unittest.SkipTest(f"mcp가 없다 ({e}). agent/.venv/bin/python으로 돌린다")

from blogops import backlog
from blogops.config import KST
from helpers import good_body, make_env

# docs/blogops.md 2절의 21개. 승인·반려는 툴이 아니다
TOOLS = {"get_system_health", "get_strategy", "get_backlog", "manage_backlog", "list_posts", "search_posts",
         "read_record", "get_git_log", "create_draft", "update_draft", "list_drafts", "get_draft", "check_quality",
         "request_approval", "get_approval_status", "publish_post", "get_post", "add_english", "request_indexing", "get_week_summary",
         "notify_human"}
SOURCE = {"title": "pre-commit.md", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/pre-commit.md"}


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name, real_clock=True)
        self.patch = mock.patch.dict(os.environ, {"BLOGOPS_ROOT": str(self.config.root),
                                                  "BLOGOPS_SITE_DIR": str(self.config.site_dir),
                                                  "BLOGOPS_CYCLE_ID": "test-cycle"})
        self.patch.start()
        os.environ.pop("BLOGOPS_NO_PUBLISH", None)
        server.reset()

    def tearDown(self):
        self.patch.stop()
        server.reset()
        self.tmp.cleanup()

    def test_tool_list(self):
        tools = asyncio.run(server.server.list_tools())
        self.assertEqual({t.name for t in tools}, TOOLS)
        self.assertTrue(all(t.description for t in tools))
        create = next(t for t in tools if t.name == "create_draft")
        self.assertEqual(set(create.input_schema["required"]), {"slug", "series", "title", "description", "tags", "body"})

    def test_errors_become_results(self):
        result = server.read_record(path=".env")
        self.assertFalse(result["ok"])
        self.assertTrue(result["error"])
        self.assertFalse(server.manage_backlog(action="remove", item_id="naming")["ok"])
        self.assertFalse(server.get_approval_status(draft_id="20261008-nope")["ok"])

    def test_draft_flow(self):
        os.environ["BLOGOPS_MODEL"] = "claude-sonnet-5-5"  # cycle.py가 넘긴다. setUp의 patch.dict가 되돌린다
        result = server.create_draft(slug="naming", series="ops-log", title="이름 짓기", description="요약",
                                     tags=["meta"], body=good_body(), sources=[SOURCE], backlog_id="naming")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "writing")
        self.assertEqual(backlog.items(self.config, "drafting")[0]["id"], "naming")
        draft_id = result["draft_id"]
        result = server.update_draft(draft_id=draft_id, note="제목에 결과를 넣었다", title="이름 짓기: 후보 5개에서 고른 이유")
        self.assertTrue(result["ok"], result)
        drafts = server.list_drafts()["drafts"]
        self.assertEqual((drafts[0]["title"], drafts[0]["status"]), ("이름 짓기: 후보 5개에서 고른 이유", "writing"))
        self.assertFalse(server.request_approval(draft_id=draft_id)["ok"])  # 품질 검사 전
        draft = server.get_draft(draft_id=draft_id)  # 고치기 전에 본문까지 읽을 수 있다
        self.assertTrue(draft["ok"], draft)
        self.assertEqual(draft["langs"]["ko"]["title"], "이름 짓기: 후보 5개에서 고른 이유")
        self.assertEqual(draft["langs"]["ko"]["body"].strip(), good_body().strip())
        self.assertEqual(draft["sources"], [SOURCE])
        self.assertEqual((draft["status"], draft["last_rejection"]), ("writing", None))
        self.assertEqual(self.store.meta(draft_id)["model"], "claude-sonnet-5-5")
        self.assertFalse(server.get_draft(draft_id="20261008-nope")["ok"])

    def test_strategy_carries_past_rejections(self):
        # 사이클마다 기억 없이 깨어나므로, 다른 초안에서 받은 반려 사유도 글을 쓰기 전에 보이게 한다
        (self.config.state_dir / "strategy.md").write_text("# 전략\n", encoding="utf-8")
        result = server.get_strategy()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["rejections"], [])
        draft_id = server.create_draft(slug="naming", series="ops-log", title="gitleaks 7.2초", description="요약",
                                       tags=["meta"], body=good_body())["draft_id"]
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        self.store.record_decision(draft_id, "rejected", reason="제목에 전문용어만 있다")
        server.update_draft(draft_id=draft_id, note="제목을 풀었다", title="비밀키 검사가 느렸던 이유")
        (rejection,) = server.get_strategy()["rejections"]
        # 반려한 판의 제목을 보여 준다 (지금 제목이 아니라)
        self.assertEqual((rejection["draft_id"], rejection["title"], rejection["reason"]),
                         (draft_id, "gitleaks 7.2초", "제목에 전문용어만 있다"))

    def test_publish_blocked_in_dry_run_and_indexing_skipped(self):
        with mock.patch.dict(os.environ, {"BLOGOPS_NO_PUBLISH": "1"}):
            result = server.publish_post(draft_id="20261008-naming")
        self.assertFalse(result["ok"])
        self.assertIn("시험 실행", result["error"])
        self.assertTrue(server.request_indexing(urls=["https://example.org/posts/a/"])["skipped"])

    def test_tool_limit_and_log(self):
        for _ in range(self.config.max_tool_calls_per_cycle):
            self.assertTrue(server.list_drafts()["ok"])
        result = server.list_drafts()
        self.assertFalse(result["ok"])
        self.assertIn("상한", result["error"])
        day = datetime.now(KST).date().isoformat()
        events = [json.loads(line) for line in (self.config.logs_dir / f"{day}.jsonl").read_text().splitlines()]
        calls = [e for e in events if e["event"] == "tool_call"]
        self.assertEqual(len(calls), self.config.max_tool_calls_per_cycle + 1)
        self.assertEqual({e["cycle"] for e in calls}, {"test-cycle"})
        self.assertEqual(sum(e["event"] == "tool_limit" for e in events), 1)

    def test_long_args_are_not_logged(self):
        server.create_draft(slug="naming", series="ops-log", title="이름 짓기", description="요약",
                            tags=["meta"], body=good_body())
        day = datetime.now(KST).date().isoformat()
        call = json.loads((self.config.logs_dir / f"{day}.jsonl").read_text().splitlines()[-1])
        self.assertRegex(call["args"]["body"], r"^<\d+자>$")


if __name__ == "__main__":
    unittest.main()
