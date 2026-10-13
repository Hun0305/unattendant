"""러너 시험. 모델을 돌리지 않는다: llama-bench 자리에 가짜 스크립트를 쓴다.

    python3 -m unittest discover -s experiments/runner -p 'test_*.py'
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import KST  # noqa: E402
from night import deadline_for, job_key, pending  # noqa: E402
from telemetry import judge  # noqa: E402

FAKE_BENCH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, sys, time
    a = sys.argv[1:]
    def opt(name, default="0"):
        return a[a.index(name) + 1] if name in a else default
    print("fake llama-bench: loading model", file=sys.stderr)
    time.sleep(float(__import__("os").environ.get("FAKE_SLEEP", "1.5")))
    n = int(opt("-r", "5"))
    print(json.dumps({"model_type": "fake", "n_prompt": int(opt("-p")), "n_gen": int(opt("-n")),
                      "n_depth": int(opt("-d")), "n_threads": int(opt("-t")), "avg_ts": 12.5,
                      "stddev_ts": 0.25, "samples_ts": [12.5] * n, "use_mmap": opt("--load-mode") != "none"}))
""")


def row(t, temp=45.0, thr=0, swin=0, swout=0, other=1.0, maj=0):
    return {"t": t, "temp_c": temp, "arm_mhz": 1800, "throttled": thr, "pswpin": swin, "pswpout": swout,
            "pgmajfault": maj, "cpu_other_pct": other}


class JudgeTest(unittest.TestCase):
    def test_clean_window_is_valid(self):
        valid, reasons, stats = judge([row(0), row(1), row(2)], 45.0)
        self.assertTrue(valid, reasons)
        self.assertEqual(stats["max_temp_c"], 45.0)

    def test_each_invalid_condition(self):
        cases = {
            "스로틀링": [row(0), row(1, thr=0x2)],
            "스왑": [row(0), row(1, swin=200, swout=100)],
            "다른 프로세스": [row(0, other=9.0), row(1, other=7.0)],
        }
        for word, rows in cases.items():
            valid, reasons, _ = judge(rows, 45.0)
            self.assertFalse(valid, word)
            self.assertTrue(any(word in r for r in reasons), (word, reasons))
        valid, reasons, _ = judge([row(0), row(1)], 70.0)
        self.assertFalse(valid)
        self.assertIn("시작 온도", reasons[0])

    def test_sticky_bits_are_ignored(self):  # 16~19번 비트는 "발생한 적 있음"이라 지금 측정과 무관하다
        valid, _, _ = judge([row(0, thr=0x50000), row(1, thr=0x50000)], 45.0)
        self.assertTrue(valid)


class NightTest(unittest.TestCase):
    def test_deadline(self):
        self.assertEqual(deadline_for("05:30", datetime(2026, 10, 15, 2, 0, tzinfo=KST)),
                         datetime(2026, 10, 15, 5, 30, tzinfo=KST))
        self.assertEqual(deadline_for("05:30", datetime(2026, 10, 14, 23, 0, tzinfo=KST)),
                         datetime(2026, 10, 15, 5, 30, tzinfo=KST))

    def test_pending_skips_done_and_given_up(self):
        jobs = [{"model": "a"}, {"model": "b"}, {"model": "c"}]
        state = {job_key(0, jobs[0]): {"status": "done"}, job_key(1, jobs[1]): {"status": "failed", "fails": 2}}
        self.assertEqual([j["model"] for _, j in pending(jobs, state)], ["c"])
        jobs[0] = {"model": "a", "threads": [1]}  # 작업 내용이 바뀌면 다시 돈다
        self.assertEqual([j["model"] for _, j in pending(jobs, state)], ["a", "c"])


class LlmBenchEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exp-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        models = self.tmp / "models"
        models.mkdir()
        (models / "fake.gguf").write_bytes(b"GGUF" + b"\0" * 12)
        (self.tmp / "models.toml").write_text(textwrap.dedent("""\
            [[model]]
            id = "fake-1b"
            name = "Fake"
            groups = ["round1"]
              [[model.file]]
              quant = "Q4_K_M"
              repo = "x/y"
              revision = "0"
              file = "fake.gguf"
              size = 16
              sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
              arch = "llama"
            """))
        bench = self.tmp / "fake-llama-bench"
        bench.write_text(FAKE_BENCH)
        bench.chmod(0o755)
        self.env = dict(os.environ, EXP_MODELS_TOML=str(self.tmp / "models.toml"), EXP_MODELS_DIR=str(models),
                        EXP_LLAMA_BENCH=str(bench), EXP_RESULTS_DIR=str(self.tmp / "results"),
                        EXP_LOGS_DIR=str(self.tmp / "logs"), EXP_START_TEMP_MAX="100",
                        EXP_VSCODE_MARKER="/exp-test-no-such-process/")  # 지금 붙어 있는 진짜 VS Code는 무시

    def run_py(self, code: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-c", code], cwd=HERE, env=self.env, capture_output=True,
                              text=True, timeout=120)

    def test_run_job_writes_results(self):
        out = self.run_py("import json, llm_bench; s = llm_bench.run_job({'model': 'fake-1b', 'tests': "
                          "['pp512', 'tg128@d2048'], 'threads': [4]}); print('SUMMARY', json.dumps(s))")
        self.assertEqual(out.returncode, 0, out.stderr)
        summary = json.loads(out.stdout.split("SUMMARY", 1)[1])
        run_dir = self.tmp / "results" / "llm-bench" / summary["run_id"]
        for name in ("conditions.json", "bench.jsonl", "summary.json", "telemetry.csv.gz", "stderr.log.gz"):
            self.assertTrue((run_dir / name).exists(), name)
        records = [json.loads(line) for line in (run_dir / "bench.jsonl").read_text().splitlines()]
        first = records[0]
        self.assertIn("--load-mode", first["cmd"])
        self.assertEqual(first["cmd"][first["cmd"].index("--load-mode") + 1], "none")
        self.assertEqual(first["results"][0]["n_prompt"], 512)
        depth = [r for r in records if r["test"] == "tg128@d2048"][0]
        self.assertEqual(depth["results"][0]["n_depth"], 2048)
        self.assertEqual(len(depth["results"][0]["samples_ts"]), 3)  # 깊이 시험은 3회
        self.assertGreater(depth["peak_rss_mb"], 0)
        with gzip.open(run_dir / "telemetry.csv.gz", "rt") as f:
            self.assertGreater(len(list(csv.DictReader(f))), 1)
        with (self.tmp / "results" / "llm-bench" / "summary.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual({r["test"] for r in rows}, {"pp512", "tg128@d2048"})
        self.assertEqual(rows[0]["avg_ts"], "12.5")
        conditions = json.loads((run_dir / "conditions.json").read_text())
        self.assertEqual(conditions["template"]["id"], "llm-bench")
        self.assertIn("mb_per_s", conditions["model_file_cold_read"])
        self.assertIn("cpu_features", conditions["system"])

    def test_stops_when_too_hot(self):  # 상한을 1°C로 낮춰 지금 온도로 멈추게 한다
        self.env.update(EXP_TEMP_ABORT="1", FAKE_SLEEP="30")
        out = self.run_py("import json, llm_bench; s = llm_bench.run_job({'model': 'fake-1b', 'tests': ['tg128'], "
                          "'threads': [4]}); print('SUMMARY', json.dumps(s))")
        self.assertEqual(out.returncode, 0, out.stderr)
        summary = json.loads(out.stdout.split("SUMMARY", 1)[1])
        run_dir = self.tmp / "results" / "llm-bench" / summary["run_id"]
        records = [json.loads(line) for line in (run_dir / "bench.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 1)  # 과열로 멈춘 것은 다시 재지 않는다
        self.assertEqual(records[0]["interrupted"], "temp")
        self.assertLess(records[0]["seconds"], 25)
        self.assertFalse(records[0]["valid"])

    def test_aborts_when_vscode_appears(self):
        marker = f"/exp-test-vscode-{os.getpid()}/"
        dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", marker])
        self.addCleanup(dummy.kill)
        self.env.update(EXP_VSCODE_MARKER=marker, FAKE_SLEEP="30")
        out = self.run_py("import json, llm_bench; s = llm_bench.run_job({'model': 'fake-1b', 'tests': ['pp512', 'tg128'], "
                          "'threads': [4]}); print('SUMMARY', json.dumps(s))")
        self.assertEqual(out.returncode, 0, out.stderr)
        summary = json.loads(out.stdout.split("SUMMARY", 1)[1])
        self.assertEqual(summary["aborted"], "vscode")
        run_dir = self.tmp / "results" / "llm-bench" / summary["run_id"]
        records = [json.loads(line) for line in (run_dir / "bench.jsonl").read_text().splitlines()]
        self.assertEqual([r["interrupted"] for r in records], ["vscode"])  # 다음 시험으로 넘어가지 않는다
        self.assertEqual(json.loads((run_dir / "summary.json").read_text())["aborted"], "vscode")

    def test_one_run_at_a_time(self):
        code = "import common; lock = common.acquire_lock(); print('LOCK', lock is not None, flush=True)"
        holder = subprocess.Popen([sys.executable, "-c", code + "; import time; time.sleep(20)"], cwd=HERE,
                                  env=self.env, stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "LOCK True")
        self.assertIn("LOCK False", self.run_py(code).stdout)

    def test_rejects_params_out_of_range(self):
        out = self.run_py("import llm_bench; llm_bench.run_job({'model': 'fake-1b', 'threads': [8]})")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("범위 밖", out.stderr)

    def test_refuses_without_memory_limit(self):
        out = subprocess.run([sys.executable, "llm_bench.py", "--model", "fake-1b"], cwd=HERE, env=self.env,
                             capture_output=True, text=True, timeout=60)
        if out.returncode == 2:
            self.assertIn("MemoryMax", out.stderr)
        else:  # 이미 메모리 상한이 걸린 유닛 안에서 시험을 돌린 경우
            self.skipTest("이 셸에 이미 메모리 상한이 걸려 있다")


if __name__ == "__main__":
    unittest.main()
