"""llm-tasks 러너 시험. 모델을 돌리지 않는다: llama-server 자리에 가짜 서버를 쓴다.

    python3 -m unittest discover -s experiments/runner -p 'test_*.py'
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTSET = HERE.parent / "promptsets" / "llm-tasks-v1"

# llama-server 흉내: /health, /v1/chat/completions(스트리밍). 마지막 user 메시지로 정답을 찾아 돌려준다
FAKE_SERVER = textwrap.dedent("""\
    #!/usr/bin/env python3
    import http.server, json, os, sys, time
    args = sys.argv[1:]
    port = int(args[args.index("--port") + 1])
    answers = json.load(open(os.environ["FAKE_ANSWERS"], encoding="utf-8"))
    log_path = os.environ.get("FAKE_REQUEST_LOG")
    ready_at = time.time() + 0.3
    print("fake llama-server", " ".join(args), flush=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a):
            pass
        def do_GET(self):
            ok = self.path == "/health" and time.time() >= ready_at
            body = b'{"status":"ok"}' if ok else b'{"error":"loading"}'
            self.send_response(200 if ok else 503)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def chunk(self, data):
            self.wfile.write(f"{len(data):x}\\r\\n".encode() + data + b"\\r\\n")
            self.wfile.flush()
        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if log_path:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({k: v for k, v in req.items() if k != "messages"} |
                                       {"system": req["messages"][0]["content"][:40]}, ensure_ascii=False) + "\\n")
            text = answers.get(req["messages"][-1]["content"], "모름")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            pieces = [text[i:i + 7] for i in range(0, len(text), 7)]
            for p in pieces:
                delta = {"choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]}
                self.chunk(("data: " + json.dumps(delta, ensure_ascii=False) + "\\n\\n").encode())
            last = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "timings": {"prompt_n": 120, "prompt_ms": 60.0, "predicted_n": len(pieces), "predicted_ms": 30.0}}
            self.chunk(("data: " + json.dumps(last) + "\\n\\n").encode())
            self.chunk(b"data: [DONE]\\n\\n")
            self.wfile.write(b"0\\r\\n\\r\\n")
            self.wfile.flush()

    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
""")


class LlmTasksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exp-tasks-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        models = self.tmp / "models"
        models.mkdir()
        (models / "fake.gguf").write_bytes(b"GGUF" + b"\0" * 12)
        (self.tmp / "models.toml").write_text(textwrap.dedent("""\
            [[model]]
            id = "fake-1b"
            name = "Fake"
              [[model.file]]
              quant = "Q4_K_M"
              repo = "x/y"
              revision = "0"
              file = "fake.gguf"
              size = 16
              sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
              arch = "llama"
            """))
        server = self.tmp / "fake-llama-server"
        server.write_text(FAKE_SERVER)
        server.chmod(0o755)
        # 정답표: 채점기가 정답을 응답 모양으로 바꾼 것 (score.gold_as_output)
        import importlib.util
        spec = importlib.util.spec_from_file_location("score_for_test", PROMPTSET / "score.py")
        score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(score)
        answers = {it["input"]: score.gold_as_output(task, it) for task in score.TASKS for it in score.load_items(task)}
        (self.tmp / "answers.json").write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")
        self.log = self.tmp / "requests.jsonl"
        self.env = dict(os.environ, EXP_MODELS_TOML=str(self.tmp / "models.toml"), EXP_MODELS_DIR=str(models),
                        EXP_LLAMA_SERVER=str(server), EXP_RESULTS_DIR=str(self.tmp / "results"),
                        EXP_LOGS_DIR=str(self.tmp / "logs"), EXP_START_TEMP_MAX="100",
                        EXP_VSCODE_MARKER="/exp-test-no-such-process/", FAKE_ANSWERS=str(self.tmp / "answers.json"),
                        FAKE_REQUEST_LOG=str(self.log))

    def run_job(self, job: dict) -> dict:
        code = f"import json, llm_tasks; s = llm_tasks.run_job({job!r}); print('SUMMARY', json.dumps(s, ensure_ascii=False))"
        out = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=self.env, capture_output=True, text=True,
                             timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        return json.loads(out.stdout.split("SUMMARY", 1)[1])

    def requests(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_full_run_scores_and_writes(self):
        summary = self.run_job({"model": "fake-1b"})
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["headline"].split(",")[0], "정답 100/100")
        self.assertEqual(summary["determinism"], {"items": 10, "same": 10, "different": []})
        self.assertEqual(len(summary["cold_load_s"]), 3)
        self.assertEqual(summary["promptset_status"], "draft")
        run_dir = self.tmp / "results" / "llm-tasks" / summary["run_id"]
        items = [json.loads(line) for line in (run_dir / "items.jsonl").read_text().splitlines()]
        self.assertEqual(len(items), 100)
        self.assertTrue(all(it["ttft_s"] is not None and it["finish_reason"] == "stop" for it in items))
        self.assertTrue(all(it["score"]["correct"] for it in items))
        for name in ("conditions.json", "summary.json", "telemetry.csv.gz", "server.log.gz"):
            self.assertTrue((run_dir / name).exists(), name)
        with (run_dir.parent / "summary.csv").open() as f:
            rows = {r["task"]: r for r in csv.DictReader(f)}
        self.assertEqual(set(rows), {"t1", "t2", "t3", "t4", "all"})
        self.assertEqual(rows["t1"]["accuracy_pct"], "100.0")
        self.assertEqual(rows["t1"]["schema_ok"], "30")
        self.assertEqual(rows["t3"]["fields_correct"], "80")
        self.assertEqual(rows["all"]["prompt_tps_p50"], "2000.0")  # 가짜 timings: 120토큰 / 60ms
        conditions = json.loads((run_dir / "conditions.json").read_text())
        self.assertEqual(conditions["promptset"]["status"], "draft")
        self.assertEqual(len(conditions["promptset"]["sha256"]), 12)
        # 요청: 그리디, 프롬프트 캐시 끔, 생각 모드 끔, 과제별 최대 토큰, JSON 제약 없음
        reqs = self.requests()
        self.assertEqual(len(reqs), 110)  # 100문항 + 결정성 확인 10문항
        self.assertTrue(all(r["temperature"] == 0 and r["cache_prompt"] is False and r["stream"] for r in reqs))
        self.assertTrue(all(r["chat_template_kwargs"] == {"enable_thinking": False} for r in reqs))
        self.assertEqual({r["max_tokens"] for r in reqs}, {192, 16, 128})
        self.assertFalse(any("response_format" in r for r in reqs))
        # 서버 실행 인자: mmap 끔, 캐시 끔, 생각 모드 끔
        log = subprocess.run(["zcat", str(run_dir / "server.log.gz")], capture_output=True, text=True).stdout
        for flag in ("-lm none", "--no-cache-prompt", "--cache-ram 0", "--reasoning off", "-np 1", "--fit off"):
            self.assertIn(flag, log)

    def test_json_constraint_only_on_t1(self):
        summary = self.run_job({"model": "fake-1b", "json_constraint": True})
        self.assertTrue(summary["run_id"].endswith("-json"))
        reqs = self.requests()
        t1 = [r for r in reqs if r["max_tokens"] == 192]
        others = [r for r in reqs if r["max_tokens"] != 192]
        self.assertTrue(t1 and all(r["response_format"]["type"] == "json_schema" for r in t1))
        self.assertNotIn("$comment", t1[0]["response_format"]["json_schema"]["schema"])
        self.assertFalse(any("response_format" in r for r in others))

    def test_aborts_when_vscode_appears(self):
        marker = f"/exp-test-vscode-{os.getpid()}/"
        dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", marker])
        self.addCleanup(dummy.kill)
        self.env["EXP_VSCODE_MARKER"] = marker
        summary = self.run_job({"model": "fake-1b"})
        self.assertEqual(summary["aborted"], "vscode")
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["determinism"], None)

    def test_rejects_params_out_of_range(self):
        code = "import llm_tasks; llm_tasks.run_job({'model': 'fake-1b', 'quant': 'Q3_K'})"
        out = subprocess.run([sys.executable, "-c", code], cwd=HERE, env=self.env, capture_output=True, text=True,
                             timeout=60)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("범위 밖", out.stderr)


if __name__ == "__main__":
    unittest.main()
