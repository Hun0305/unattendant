import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import cycle, log
from helpers import REAL_ROOT, make_env
from test_notify import FAKE_ENV, FakeTransport

# 가짜 claude: 받은 인자·환경·MCP 설정을 FAKE_CLAUDE_OUT에 적고, FAKE_CLAUDE_MODE대로 답한다
FAKE_CLAUDE = """#!{python}
import json, os, sys, time
args = sys.argv[1:]
mcp = json.load(open(args[args.index("--mcp-config") + 1]))
cycle_id = mcp["mcpServers"]["blogops"]["env"]["BLOGOPS_CYCLE_ID"]
json.dump({{"args": args, "stdin": sys.stdin.read(), "cwd": os.getcwd(), "mcp": mcp,
           "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"), "config_dir": os.environ.get("CLAUDE_CONFIG_DIR"),
           "api_key": os.environ.get("ANTHROPIC_API_KEY"), "claudecode": os.environ.get("CLAUDECODE")}},
          open(os.environ["FAKE_CLAUDE_OUT"], "w"), ensure_ascii=False)
mode = os.environ["FAKE_CLAUDE_MODE"]
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as f:  # MCP 서버가 남기는 툴 호출 기록 흉내
    for tool, ok in (("get_system_health", True), ("check_quality", False)):
        f.write(json.dumps({{"event": "tool_call", "cycle": cycle_id, "tool": tool, "ok": ok}}) + "\\n")
    f.write(json.dumps({{"event": "tool_call", "cycle": "other", "tool": "list_drafts", "ok": True}}) + "\\n")
    if mode == "limit":
        f.write(json.dumps({{"event": "tool_limit", "cycle": cycle_id}}) + "\\n")
if mode == "sleep":
    time.sleep(30)
if mode == "garbage":
    print("not json")
    sys.exit(1)
error = mode == "fail"
print(json.dumps({{"type": "result", "subtype": "error_during_execution" if error else "success",
                  "is_error": error, "num_turns": 12, "duration_api_ms": 61000, "total_cost_usd": 0.4321,
                  "modelUsage": {{"claude-sonnet-5-5": {{"inputTokens": 10, "outputTokens": 20}}}},
                  "permission_denials": [], "result": "사용 한도에 걸렸다" if error else "초안을 만들고 승인을 요청했다"}}))
sys.exit(1 if error else 0)
"""


class CycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.config, _ = make_env(self.tmp.name)
        shutil.copytree(REAL_ROOT / "ops" / "huninn", self.config.root / "ops" / "huninn")
        fake = tmp / "fake-claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
        fake.chmod(0o755)
        env_file = tmp / "huninn.env"
        env_file.write_text(FAKE_ENV + "CLAUDE_CODE_OAUTH_TOKEN=test-oauth-token\n", encoding="utf-8")
        self.out = tmp / "claude-call.json"
        self.patch = mock.patch.dict(os.environ, {
            "HUNINN_CLAUDE": str(fake), "HUNINN_HOME": str(tmp / "huninn"), "BLOGOPS_ENV_FILE": str(env_file),
            "BLOGOPS_SITE_DIR": str(self.config.site_dir), "BLOGOPS_NO_PUBLISH": "1",
            "FAKE_CLAUDE_OUT": str(self.out), "FAKE_CLAUDE_LOG": str(self.config.logs_dir / "2026-10-08.jsonl"),
            "FAKE_CLAUDE_MODE": "ok", "ANTHROPIC_API_KEY": "should-not-pass", "CLAUDECODE": "1",
            "CLAUDE_CONFIG_DIR": str(tmp / "human-claude")})
        self.patch.start()
        for key in ("HUNINN_MODEL", "CLAUDE_CODE_OAUTH_TOKEN"):
            os.environ.pop(key, None)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def cycles(self):
        return [json.loads(line) for line in (self.config.logs_dir / "cycles.jsonl").read_text().splitlines()]

    def test_success(self):
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertFalse(record["is_error"])
        self.assertEqual(t.calls, [])  # 잘 끝나면 알리지 않는다 (일일 요약은 Huninn이 보낸다)
        self.assertEqual(self.cycles(), [record])
        self.assertEqual(record["total_cost_usd"], 0.4321)
        self.assertTrue(record["estimate"])
        self.assertTrue(record["dry_run"])
        self.assertEqual(record["model"], cycle.DEFAULT_MODEL)
        self.assertEqual((record["tool_calls"], record["tool_errors"]), (2, 1))  # 다른 사이클 기록은 세지 않는다

        call = json.loads(self.out.read_text())
        args = call["args"]
        self.assertEqual(args[args.index("--tools") + 1], "")
        for flag in ("--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--setting-sources") + 1], "user")
        self.assertEqual(args[args.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(args[args.index("--model") + 1], cycle.DEFAULT_MODEL)
        self.assertTrue(args[args.index("--system-prompt") + 1].startswith("너는 Huninn이다"))
        self.assertIn("시험 실행", call["stdin"])
        self.assertIn(record["cycle"], call["stdin"])
        # 레포 밖에서 돌고, 구독 토큰만 넘어가고, 사람 세션 변수는 넘어가지 않는다
        self.assertFalse(Path(call["cwd"]).is_relative_to(self.config.root))
        self.assertEqual(call["token"], "test-oauth-token")
        self.assertEqual(call["config_dir"], str(Path(os.environ["HUNINN_HOME"]) / "claude"))
        self.assertIsNone(call["api_key"])
        self.assertIsNone(call["claudecode"])
        server = call["mcp"]["mcpServers"]["blogops"]
        self.assertEqual(server["command"], f"{self.config.root}/agent/.venv/bin/python")
        self.assertEqual(server["env"]["BLOGOPS_ROOT"], str(self.config.root))
        self.assertEqual(server["env"]["BLOGOPS_CYCLE_ID"], record["cycle"])
        self.assertEqual(server["env"]["BLOGOPS_NO_PUBLISH"], "1")
        self.assertEqual(server["env"]["BLOGOPS_SITE_DIR"], str(self.config.site_dir))

    def test_failure_alerts(self):
        os.environ["FAKE_CLAUDE_MODE"] = "fail"
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertTrue(record["is_error"])
        url, _, payload = t.calls[0]
        self.assertTrue(url.endswith("/channels/101/messages"))  # #긴급
        self.assertTrue(payload["content"].startswith("<@222> **긴급**"))
        self.assertIn("사용 한도에 걸렸다", payload["content"])

        os.environ["FAKE_CLAUDE_MODE"] = "garbage"
        record = cycle.run(self.config, transport=FakeTransport((500, {})))
        self.assertTrue(record["is_error"])
        self.assertEqual(record["output"], "not json")
        self.assertIn("notify_error", record)  # 알림이 실패해도 기록은 남긴다
        self.assertEqual(len(self.cycles()), 2)

    def test_timeout(self):
        os.environ["FAKE_CLAUDE_MODE"] = "sleep"
        t = FakeTransport()
        record = cycle.run(self.config, timeout=1, transport=t)
        self.assertTrue(record["timed_out"])
        self.assertTrue(record["is_error"])
        self.assertIn("시간 제한", t.calls[0][2]["content"])

    def test_tool_limit_warns(self):
        os.environ["FAKE_CLAUDE_MODE"] = "limit"
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertFalse(record["is_error"])
        self.assertTrue(record["tool_limit_hit"])
        self.assertTrue(t.calls[0][2]["content"].startswith("**주의**"))

    def test_missing_token(self):
        Path(os.environ["BLOGOPS_ENV_FILE"]).write_text(FAKE_ENV, encoding="utf-8")
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertTrue(record["is_error"])
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", record["error"])
        self.assertFalse(self.out.exists())  # claude를 부르지 않았다
        self.assertEqual(len(t.calls), 1)

    def test_one_cycle_at_a_time(self):
        import fcntl
        self.config.logs_dir.mkdir(exist_ok=True)
        with open(self.config.logs_dir / ".cycle.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaises(cycle.CycleError):
                cycle.run(self.config, transport=FakeTransport())

    def test_week_summary_reads_cycles(self):
        from blogops import summary
        from blogops.store import Store
        cycle.run(self.config, transport=FakeTransport())
        os.environ["FAKE_CLAUDE_MODE"] = "fail"
        cycle.run(self.config, transport=FakeTransport())
        week = summary.week(self.config, Store(self.config))
        self.assertEqual((week["cycles"]["count"], week["cycles"]["failed"]), (2, 1))
        self.assertAlmostEqual(week["cycles"]["cost_usd_estimate"], 0.8642)


class ToolStatsTest(unittest.TestCase):
    def test_counts_only_this_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = make_env(tmp)
            guard = log.CycleGuard(config, cycle_id="c1")
            guard.check("list_drafts")
            guard.record("list_drafts", True, 3)
            log.CycleGuard(config, cycle_id="c2").record("list_drafts", False, 3)
            day = config.now().date().isoformat()
            self.assertEqual(cycle.tool_stats(config, "c1", {day})["tool_calls"], 1)
            self.assertEqual(cycle.tool_stats(config, "c2", {day})["tool_errors"], 1)


if __name__ == "__main__":
    unittest.main()
