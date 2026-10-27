"""상태 점검: 사이클을 멈추는 problems와 알리기만 하는 notices"""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from blogops import health
from helpers import make_env


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name)
        patcher = mock.patch.object(health.urllib.request, "urlopen", return_value=FakeResponse())
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, bot="active", age=3.0):
        return health.check(self.config, self.store, bot_state=lambda unit: bot, status_age=lambda config: age)

    def test_all_good(self):
        result = self.check()
        self.assertEqual((result["ok"], result["problems"], result["notices"]), (True, [], []))
        self.assertEqual(result["services"], {"bot": "active", "status_file_age_min": 3.0, "last_cycle": None})

    def test_bot_down_is_a_notice_not_a_problem(self):
        result = self.check(bot="failed")
        self.assertTrue(result["ok"])  # 발행·글쓰기는 계속한다
        self.assertEqual(len(result["notices"]), 1)
        self.assertIn("review", result["notices"][0])
        self.assertEqual(self.check(bot="unknown")["notices"], [])  # systemctl을 못 부르면 조용히

    def test_status_file_stale_or_missing(self):
        self.assertIn("갱신되지 않았다", self.check(age=45)["notices"][0])
        self.assertIn("없다", self.check(age=None)["notices"][0])
        self.assertTrue(self.check(age=None)["ok"])

    def test_status_file_age(self):
        path = Path(self.tmp.name) / "status.json"
        updated = self.config.now() - timedelta(minutes=12)
        path.write_text(json.dumps({"updated": updated.isoformat(timespec="seconds")}))
        self.assertAlmostEqual(health.status_file_age_min(self.config, path), 12.0, delta=0.1)
        path.write_text("{")
        self.assertIsNone(health.status_file_age_min(self.config, path))
        self.assertIsNone(health.status_file_age_min(self.config, Path(self.tmp.name) / "없음.json"))

    def test_unit_state_real_systemctl(self):
        self.assertIsInstance(health.unit_state("huninn-bot.service"), str)


    def test_failed_last_cycle_is_a_notice(self):
        # 토큰이 풀려 며칠 실패하다 다시 돈 날: 멈추지 않고, 요약에 복구를 적게 알린다
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.config.logs_dir / "cycles.jsonl").write_text(
            json.dumps({"ts": "2026-10-17T14:00:14+09:00", "is_error": True}) + "\n"
            + json.dumps({"ts": "2026-10-18T14:00:14+09:00", "is_error": True}) + "\n", encoding="utf-8")
        result = self.check()
        self.assertTrue(result["ok"])
        self.assertTrue(any("2026-10-17부터 2회 연속" in n for n in result["notices"]), result["notices"])
        self.assertEqual(result["services"]["last_cycle"]["fail_streak"], 2)


if __name__ == "__main__":
    unittest.main()
