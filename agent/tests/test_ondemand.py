import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from blogops import ondemand
from blogops.config import KST, Config
from helpers import make_env


def systemctl_output(state="active", *paths):
    lines = [f"ActiveState={state}"] + [f"Paths={p} (PathExists)" for p in paths]
    return lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout="\n".join(lines) + "\n", stderr="")


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, _ = make_env(self.tmp.name)
        self.mine = str(self.config.cycle_request_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_active_and_watching_this_file(self):
        self.assertTrue(ondemand.watcher_active(self.config, run=systemctl_output("active", self.mine)))

    def test_watching_another_checkout_is_not_ours(self):
        # 매장을 지켜보는 유닛은 작업실이나 시험용 임시 폴더의 요청 파일에는 반응하지 않는다
        other = "/home/hun/unattendant-live/logs/.cycle-request"
        self.assertFalse(ondemand.watcher_active(self.config, run=systemctl_output("active", other)))

    def test_inactive_or_not_installed(self):
        self.assertFalse(ondemand.watcher_active(self.config, run=systemctl_output("inactive", self.mine)))
        self.assertFalse(ondemand.watcher_active(self.config, run=systemctl_output("inactive")))  # 설치 전: not-found

    def test_systemctl_problems_mean_not_watching(self):
        def missing(*a, **k):
            raise FileNotFoundError("systemctl")

        def hangs(*a, **k):
            raise subprocess.TimeoutExpired("systemctl", 5)

        self.assertFalse(ondemand.watcher_active(self.config, run=missing))
        self.assertFalse(ondemand.watcher_active(self.config, run=hangs))

    def test_real_systemctl_does_not_break(self):
        # 실제 systemctl로 불러 본다. 이 Pi에 유닛이 없거나 다른 경로를 보면 False, 있어도 예외는 없다
        self.assertIn(ondemand.watcher_active(self.config), (False, True))


class RequestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, _ = make_env(self.tmp.name)
        self.watch = mock.patch.object(ondemand, "watcher_active", return_value=True)
        self.watch.start()

    def tearDown(self):
        self.watch.stop()
        self.tmp.cleanup()

    def events(self):
        return [r for f in sorted(self.config.logs_dir.glob("*.jsonl"))
                for r in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if "event" in r]

    def test_request_writes_file_and_logs(self):
        result = ondemand.request(self.config, "rejected", "20261013-naming")
        self.assertEqual(result, {"status": "requested", "count": 1, "limit": 5})
        body = json.loads(self.config.cycle_request_path.read_text(encoding="utf-8"))
        self.assertEqual((body["kind"], body["draft_id"]), ("rejected", "20261013-naming"))
        (event,) = [e for e in self.events() if e["event"] == "cycle_requested"]
        self.assertEqual((event["granted"], event["n"], event["actor"]), (True, 1, "operator"))

    def test_daily_limit(self):
        for n in range(1, 6):
            self.assertEqual(ondemand.request(self.config, "dropped", f"20261013-a{n}")["count"], n)
            self.config.cycle_request_path.unlink()  # 서비스가 시작하며 지운다
        result = ondemand.request(self.config, "rejected", "20261013-a6")
        self.assertEqual((result["status"], result["count"], result["limit"]), ("capped", 5, 5))
        self.assertFalse(self.config.cycle_request_path.exists())  # 상한을 넘으면 파일을 만들지 않는다
        denied = [e for e in self.events() if e["event"] == "cycle_requested" and not e["granted"]]
        self.assertEqual([e["reason"] for e in denied], ["capped"])

    def test_limit_resets_next_day(self):
        for n in range(5):
            ondemand.request(self.config, "dropped", f"20261013-a{n}")
        tomorrow = Config(root=self.config.root, site_root=self.config.site_root,
                          clock=lambda: datetime(2026, 10, 9, 9, 0, tzinfo=KST))  # 시험 시계는 10-08 14:00에서 시작한다
        self.assertEqual(ondemand.request(tomorrow, "dropped", "20261009-b")["status"], "requested")

    def test_unwatched_does_nothing(self):
        with mock.patch.object(ondemand, "watcher_active", return_value=False):
            result = ondemand.request(self.config, "rejected", "20261013-naming")
        self.assertEqual(result["status"], "unwatched")
        self.assertFalse(self.config.cycle_request_path.exists())

    def test_only_granted_requests_count(self):
        with mock.patch.object(ondemand, "watcher_active", return_value=False):
            for _ in range(7):
                ondemand.request(self.config, "rejected", "20261013-naming")
        self.assertEqual(ondemand.count_today(self.config), 0)
        self.assertEqual(ondemand.request(self.config, "rejected", "20261013-naming")["count"], 1)

    def test_custom_limit(self):
        config = Config(root=self.config.root, site_root=self.config.site_root, ondemand_daily_limit=1, clock=self.config.clock)
        self.assertEqual(ondemand.request(config, "rejected", "20261013-a")["status"], "requested")
        self.assertEqual(ondemand.request(config, "rejected", "20261013-b")["status"], "capped")

    def test_corrupt_log_lines_are_skipped(self):
        self.config.logs_dir.mkdir(exist_ok=True)
        today = self.config.logs_dir / f"{self.config.now():%Y-%m-%d}.jsonl"
        today.write_text('깨진 줄\n{"event": "cycle_requested", "granted": true}\n', encoding="utf-8")
        self.assertEqual(ondemand.count_today(self.config), 1)


if __name__ == "__main__":
    unittest.main()
