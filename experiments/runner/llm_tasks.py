#!/usr/bin/env python3
"""템플릿 llm-tasks: llama-server로 과제 세트를 돌려 정확도와 응답 시간을 잰다 (docs/experiments.md 5.1절, 6절, 10절).

    systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 \\
        python3 experiments/runner/llm_tasks.py --model llama-3.2-1b
    ... --model qwen3.5-2b --json-constraint      # T1에 JSON 스키마 제약 (5.3절)

- 범위와 고정값은 experiments/templates/llm-tasks/template.toml에서 읽는다
- 콜드 로드: 모델 파일을 페이지 캐시에서 비우고 서버를 띄워 /health가 응답할 때까지를 cold_starts번 잰다
- 본 측정: 서버를 한 번 띄워 문항마다 스트리밍으로 요청한다. 첫 토큰까지 시간(TTFT)은 요청을 보낸 때부터
  답의 첫 글자(content)가 올 때까지다. 서버가 낸 처리 시간(timings)도 같이 남긴다
- 그리디(temperature 0)라 정확도는 측정 환경과 상관없다. 시간 값만 문항마다 무효 판정(7.4절)을 하고,
  무효인 문항은 시간 통계에서 뺀다(정확도에는 넣는다)
- 문항 사이에 Huninn 사이클이 돌면 서버를 내리고 기다렸다가 다시 띄운다(7.1절). VS Code 서버가 뜨거나
  80°C에 닿으면 작업을 멈춘다(aborted). 다시 도는 것은 night.py가 한다
- 끝난 뒤 앞 determinism_items문항을 한 번 더 돌려 출력이 같은지 남긴다 (6절)
- 결과: experiments/results/llm-tasks/<실행 ID>/, 과제별 한 줄 요약은 experiments/results/llm-tasks/summary.csv
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import http.client
import importlib.util
import json
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from common import (EXP_DIR, LLAMA_DIR, RESULTS_DIR, TEMP_ABORT_C, acquire_lock, cgroup_value, code_version, cycle_active,
                    evict_page_cache, llama_info, loadavg1, log_event, meminfo, model_file, now, oom_kills, own_cgroup,
                    system_info, temp_c, throttled, vscode_pids, wait_cool, wait_cycle)
from telemetry import Telemetry, judge

TEMPLATE_PATH = EXP_DIR / "templates" / "llm-tasks" / "template.toml"
LLAMA_SERVER = Path(os.environ.get("EXP_LLAMA_SERVER", LLAMA_DIR / "build" / "bin" / "llama-server"))
TASK_ORDER = ("t1", "t2", "t3", "t4")
SUMMARY_FIELDS = ["run_id", "date", "model", "quant", "promptset", "promptset_status", "condition", "task", "items",
                  "correct", "accuracy_pct", "parsed", "schema_ok", "fields_correct", "drift", "ttft_p50_s",
                  "ttft_p90_s", "total_p50_s", "gen_tps_p50", "prompt_tps_p50", "timing_items", "cold_load_s",
                  "peak_rss_mb", "complete", "llama_cpp", "model_sha256"]


def load_template() -> tuple[dict, str]:
    raw = TEMPLATE_PATH.read_bytes()
    return tomllib.loads(raw.decode()), hashlib.sha256(raw).hexdigest()[:12]


def check_params(template: dict, quant: str, promptset: str, json_constraint: bool, thinking: bool) -> None:
    p = template["params"]
    for name, value, allowed in (("양자화", quant, p["quants"]), ("과제 세트", promptset, p["promptsets"]),
                                 ("JSON 제약", json_constraint, p["json_constraint"]), ("생각 모드", thinking, p["thinking"])):
        if value not in allowed:
            raise ValueError(f"{name} {value}는 범위 밖이다: {allowed}")


class Promptset:
    """과제 세트: 지시문·예시(prompts.toml), 문항(*.jsonl), 채점기(score.py), T1 스키마."""

    def __init__(self, name: str):
        self.name = name
        self.dir = EXP_DIR / "promptsets" / name
        self.prompts = tomllib.loads((self.dir / "prompts.toml").read_text(encoding="utf-8"))
        self.status = self.prompts.get("status", "unknown")
        spec = importlib.util.spec_from_file_location(f"score_{name.replace('-', '_')}", self.dir / "score.py")
        self.score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.score)
        self.items = {task: self.score.load_items(task) for task in TASK_ORDER}
        schema = json.loads((self.dir / "t1_schema.json").read_text(encoding="utf-8"))
        self.t1_schema = {k: v for k, v in schema.items() if not k.startswith("$")}
        self.sha256 = self._hash()

    def _hash(self) -> str:
        """문항, 채점기, 스키마, 지시문·예시의 해시. status 줄과 README는 넣지 않는다."""
        h = hashlib.sha256()
        body = {k: v for k, v in self.prompts.items() if k != "status"}
        h.update(json.dumps(body, sort_keys=True, ensure_ascii=False).encode())
        for f in sorted(self.dir.iterdir()):
            if f.is_file() and f.suffix in (".jsonl", ".py", ".json"):
                h.update(f.name.encode())
                h.update(f.read_bytes())
        return h.hexdigest()[:12]

    def messages(self, task: str, text: str) -> list[dict]:
        p = self.prompts[task]
        msgs = [{"role": "system", "content": p["system"].strip()}]
        for example in p["examples"]:
            msgs += [{"role": "user", "content": example["input"]}, {"role": "assistant", "content": example["output"]}]
        msgs.append({"role": "user", "content": text})
        return msgs


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """llama-server 하나. start()는 준비될 때까지 걸린 초, stop()은 최대 RSS(MB)를 돌려준다."""

    def __init__(self, path: Path, template: dict, thinking: bool, log):
        f = template["fixed"]
        self.port = free_port()
        self.log = log
        self.proc: subprocess.Popen | None = None
        self.cmd = [str(LLAMA_SERVER), "-m", str(path), "-t", str(f["threads"]), "-c", str(f["ctx_size"]),
                    "-lm", f["load_mode"], "--seed", str(f["seed"]), "--host", "127.0.0.1", "--port", str(self.port),
                    "--reasoning", "on" if thinking else "off", *f["server_args"]]

    def start(self, timeout_s: float) -> float:
        self.log.write(f"===== start {' '.join(self.cmd[1:])}\n")
        self.log.flush()
        self.proc = subprocess.Popen(self.cmd, stdout=self.log, stderr=subprocess.STDOUT)
        started = time.perf_counter()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server가 준비 전에 끝났다 (종료 코드 {self.proc.returncode})")
            if self.healthy():
                return round(time.perf_counter() - started, 2)
            if time.perf_counter() - started > timeout_s:
                self.stop()
                raise RuntimeError(f"llama-server가 {timeout_s}초 안에 준비되지 않았다")
            time.sleep(0.25)

    def healthy(self) -> bool:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.request("GET", "/health")
            response = conn.getresponse()
            response.read()
            return response.status == 200
        except OSError:
            return False
        finally:
            conn.close()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None and self.proc.poll() is None

    def stop(self) -> float | None:
        if self.proc is None or self.proc.returncode is not None:
            return None
        self.proc.send_signal(signal.SIGTERM)
        deadline = time.monotonic() + 15
        while True:
            pid, status, usage = os.wait4(self.proc.pid, os.WNOHANG)  # 이 프로세스만의 최대 RSS를 얻으려고 직접 기다린다
            if pid:
                break
            if time.monotonic() > deadline:
                self.proc.kill()
                pid, status, usage = os.wait4(self.proc.pid, 0)
                break
            time.sleep(0.1)
        self.proc.returncode = os.waitstatus_to_exitcode(status)
        return round(usage.ru_maxrss / 1024, 1)


def ask(port: int, body: dict, timeout_s: float) -> dict:
    """스트리밍 요청 하나. TTFT는 요청을 보낸 때부터 답의 첫 글자(content)까지."""
    started = time.perf_counter()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_s)
    content, reasoning = [], []
    ttft = ttft_any = None
    finish = timings = None
    try:
        conn.request("POST", "/v1/chat/completions", json.dumps(body, ensure_ascii=False).encode(),
                     {"Content-Type": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            detail = response.read()[:300].decode(errors="replace")
            return {"error": f"HTTP {response.status}: {detail}", "total_s": round(time.perf_counter() - started, 3)}
        while line := response.readline():
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                break
            chunk = json.loads(data)
            timings = chunk.get("timings", timings)
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                for key, sink in (("reasoning_content", reasoning), ("content", content)):
                    piece = delta.get(key)
                    if piece:
                        elapsed = time.perf_counter() - started
                        ttft_any = elapsed if ttft_any is None else ttft_any
                        if key == "content" and ttft is None:
                            ttft = elapsed
                        sink.append(piece)
                finish = choice.get("finish_reason") or finish
    except (OSError, ValueError, http.client.HTTPException) as e:
        return {"error": f"{type(e).__name__}: {e}", "output": "".join(content),
                "total_s": round(time.perf_counter() - started, 3)}
    finally:
        conn.close()
    return {"output": "".join(content), "reasoning": "".join(reasoning), "finish_reason": finish,
            "ttft_s": None if ttft is None else round(ttft, 3), "ttft_any_s": None if ttft_any is None else round(ttft_any, 3),
            "total_s": round(time.perf_counter() - started, 3), "timings": timings}


def request_body(ps: Promptset, template: dict, task: str, text: str, json_constraint: bool, thinking: bool) -> dict:
    f = template["fixed"]
    body = {"messages": ps.messages(task, text),
            "max_tokens": f["thinking_max_tokens"] if thinking else ps.prompts[task]["max_tokens"],
            "temperature": f["temperature"], "seed": f["seed"], "stream": True, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": thinking}}
    if json_constraint and task == "t1":
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "t1_command", "schema": ps.t1_schema}}
    return body


def interruption() -> str | None:
    if vscode_pids():  # CLAUDE.md: VS Code 원격 연결 중에는 LLM 실험을 돌리지 않는다
        return "vscode"
    t = temp_c()
    if t is not None and t >= TEMP_ABORT_C:
        return "temp"
    return None


def pct(values: list[float], p: float) -> float | None:
    """백분위 (가장 가까운 순위 방식)."""
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)], 3)


def rate(n: object, ms: object) -> float | None:
    return round(n / ms * 1000, 2) if isinstance(n, (int, float)) and isinstance(ms, (int, float)) and ms > 0 else None


def run_job(job: dict) -> dict:
    """작업 하나(모델 하나, 양자화 하나, 과제 세트 하나, 조건 하나)를 재고 결과 폴더를 쓴다. 요약을 돌려준다."""
    template, template_hash = load_template()
    quant = job.get("quant", "Q4_K_M")
    promptset = job.get("promptset", "llm-tasks-v1")
    json_constraint, thinking = bool(job.get("json_constraint", False)), bool(job.get("thinking", False))
    check_params(template, quant, promptset, json_constraint, thinking)
    model, entry, path = model_file(job["model"], quant)
    ps = Promptset(promptset)
    condition = "+".join(n for n, on in (("json", json_constraint), ("think", thinking)) if on) or "default"

    started = now()
    suffix = "" if condition == "default" else f"-{condition.replace('+', '-')}"
    run_id = f"{started:%Y%m%dT%H%M%S}-{model['id']}-{quant}-{promptset}{suffix}"
    run_dir = RESULTS_DIR / "llm-tasks" / run_id
    run_dir.mkdir(parents=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"exp-{run_id}-", dir="/tmp"))  # 실행 중 기록은 RAM에
    cg = own_cgroup()
    info = llama_info()
    conditions = {
        "run_id": run_id, "template": {"id": template["id"], "version": template["version"], "sha256": template_hash},
        "started": started.isoformat(timespec="seconds"),
        "model": {k: model.get(k) for k in ("id", "name", "maker", "released", "structure", "license", "thinking")},
        "file": entry, "promptset": {"name": promptset, "status": ps.status, "sha256": ps.sha256},
        "params": {"quant": quant, "condition": condition, "json_constraint": json_constraint, "thinking": thinking,
                   **template["fixed"]},
        "system": system_info(), "llama_cpp": info, "code": code_version(),
        "start": {"temp_c": temp_c(), "mem_available_mb": meminfo().get("MemAvailable", 0) >> 20, "load1": loadavg1(),
                  "throttled": throttled(), "vscode_processes": len(vscode_pids()),
                  "memory_max_mb": (cgroup_value(cg, "memory.max") or 0) >> 20 or None},
    }
    log_event("llm-tasks-start", run_id=run_id, model=model["id"], quant=quant, promptset=promptset,
              promptset_status=ps.status, condition=condition)

    tel = Telemetry(tmp / "telemetry.csv", cg)
    tel.start()
    server_log = (tmp / "server.log").open("w")
    records: list[dict] = []
    cold: list[float] = []
    determinism, aborted, failure, peak_rss = None, None, None, None
    ooms = oom_kills(cg)
    server = None
    try:
        conditions["start"]["cycle_wait_s"] = wait_cycle()
        conditions["start"]["temp_c"], conditions["start"]["cooldown_s"] = wait_cool()
        for _ in range(template["cold_starts"]):
            evict_page_cache(path)
            probe = Server(path, template, thinking, server_log)
            cold.append(probe.start(template["server_ready_timeout_s"]))
            probe.stop()
        server = Server(path, template, thinking, server_log)
        server.start(template["server_ready_timeout_s"])

        order = [(task, item) for task in TASK_ORDER for item in ps.items[task]]
        for task, item in order:
            if why := interruption():
                aborted = why
                break
            if cycle_active():  # 사이클에 양보한다: 서버를 내리고 끝나기를 기다린다 (7.1절)
                server.stop()
                log_event("llm-tasks-yield", run_id=run_id, item=item["id"])
                wait_cycle()
                server.start(template["server_ready_timeout_s"])
            if not server.alive():
                raise RuntimeError("llama-server가 도중에 끝났다" + (" (OOM)" if oom_kills(cg) > ooms else ""))
            t0 = time.time()
            result = ask(server.port, request_body(ps, template, task, item["input"], json_constraint, thinking),
                         template["request_timeout_s"])
            valid, reasons, stats = judge(tel.window(t0, time.time()), None)
            if result.get("error"):
                reasons.append(result["error"])
            records.append({"task": task, "id": item["id"], **result,
                            "score": ps.score.score(task, result.get("output", ""), item["gold"]),
                            "valid_timing": valid and not result.get("error"), "reasons": reasons,
                            "telemetry": {k: stats[k] for k in ("max_temp_c", "other_cpu_avg_pct")}})
        if not aborted and records:
            determinism = check_determinism(server, ps, template, order[:template["determinism_items"]], records,
                                            json_constraint, thinking)
    except Exception as e:
        failure = f"{type(e).__name__}: {e}"
        raise
    finally:
        if server is not None:
            peak_rss = server.stop()
        tel.stop()
        server_log.close()
        conditions["cold_load_s"] = cold
        conditions["peak_rss_mb"] = peak_rss
        conditions["cgroup_memory_peak_mb"] = (cgroup_value(cg, "memory.peak") or 0) >> 20 or None
        summary = write_outputs(run_dir, tmp, conditions, ps, records, determinism, aborted, failure, entry, info)
        shutil.rmtree(tmp, ignore_errors=True)
    log_event("llm-tasks-end", run_id=run_id, headline=summary["headline"], aborted=aborted)
    return summary


def check_determinism(server: Server, ps: Promptset, template: dict, subset: list[tuple[str, dict]],
                      records: list[dict], json_constraint: bool, thinking: bool) -> dict:
    """앞 문항들을 한 번 더 돌려 출력이 같은지 본다. 그리디라 같아야 한다 (6절)."""
    first = {(r["task"], r["id"]): r.get("output") for r in records}
    different = []
    for task, item in subset:
        again = ask(server.port, request_body(ps, template, task, item["input"], json_constraint, thinking),
                    template["request_timeout_s"])
        if again.get("output") != first.get((task, item["id"])):
            different.append(item["id"])
    return {"items": len(subset), "same": len(subset) - len(different), "different": different}


def write_outputs(run_dir: Path, tmp: Path, conditions: dict, ps: Promptset, records: list[dict],
                  determinism: dict | None, aborted: str | None, failure: str | None, entry: dict, info: dict) -> dict:
    (run_dir / "conditions.json").write_text(json.dumps(conditions, ensure_ascii=False, indent=2) + "\n")
    with (run_dir / "items.jsonl").open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    for name in ("telemetry.csv", "server.log"):
        if (tmp / name).exists():
            with (tmp / name).open("rb") as src, gzip.open(run_dir / f"{name}.gz", "wb") as dst:
                shutil.copyfileobj(src, dst)

    expected = sum(len(ps.items[task]) for task in TASK_ORDER)
    complete = not aborted and not failure and len(records) == expected and not any(r.get("error") for r in records)
    cold = conditions.get("cold_load_s") or []
    base = {"run_id": conditions["run_id"], "date": conditions["started"], "model": conditions["model"]["id"],
            "quant": conditions["params"]["quant"], "promptset": ps.name, "promptset_status": ps.status,
            "condition": conditions["params"]["condition"], "cold_load_s": pct(cold, 50),
            "peak_rss_mb": conditions.get("peak_rss_mb"), "complete": complete,
            "llama_cpp": f"{info.get('tag') or ''}@{(info.get('commit') or '')[:7]}", "model_sha256": entry["sha256"][:12]}
    rows = []
    for task in (*TASK_ORDER, "all"):
        recs = [r for r in records if task == "all" or r["task"] == task]
        if not recs:
            continue
        timed = [r for r in recs if r["valid_timing"] and r.get("ttft_s") is not None]
        row = {**base, "task": task, "items": len(recs), "correct": sum(r["score"]["correct"] for r in recs)}
        row["accuracy_pct"] = round(row["correct"] / len(recs) * 100, 1)
        if task != "all":
            extra = ps.score.summarize(task, [r["score"] for r in recs])
            row.update({k: extra.get(k) for k in ("parsed", "schema_ok", "fields_correct", "drift")})
        row.update({
            "ttft_p50_s": pct([r["ttft_s"] for r in timed], 50), "ttft_p90_s": pct([r["ttft_s"] for r in timed], 90),
            "total_p50_s": pct([r["total_s"] for r in timed], 50),
            "gen_tps_p50": pct([v for r in timed if (v := rate((r.get("timings") or {}).get("predicted_n"),
                                                            (r.get("timings") or {}).get("predicted_ms")))], 50),
            "prompt_tps_p50": pct([v for r in timed if (v := rate((r.get("timings") or {}).get("prompt_n"),
                                                               (r.get("timings") or {}).get("prompt_ms")))], 50),
            "timing_items": len(timed),
        })
        rows.append(row)

    overall = next((r for r in rows if r["task"] == "all"), None)
    headline = (f"정답 {overall['correct']}/{overall['items']}, 시간 유효 {overall['timing_items']}/{overall['items']}"
                if overall else "문항 없음")
    summary = {"run_id": conditions["run_id"], "promptset_status": ps.status, "complete": complete, "aborted": aborted,
               "failure": failure, "determinism": determinism, "cold_load_s": cold, "headline": headline, "rows": rows}
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    table = run_dir.parent / "summary.csv"
    new = not table.exists()
    with table.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerows(rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="과제 세트 정확도와 응답 시간 (템플릿 llm-tasks)")
    parser.add_argument("--model", required=True, help="models.toml의 id")
    parser.add_argument("--quant", default="Q4_K_M")
    parser.add_argument("--promptset", default="llm-tasks-v1")
    parser.add_argument("--json-constraint", action="store_true", help="T1에 JSON 스키마 제약")
    parser.add_argument("--thinking", action="store_true", help="생각 모드 켜기")
    args = parser.parse_args()
    if cgroup_value(own_cgroup(), "memory.max") is None:
        print("메모리 상한 없이 실행할 수 없다 (CLAUDE.md: 실험은 systemd 서비스 + MemoryMax로만).\n"
              "예: systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 "
              "python3 experiments/runner/llm_tasks.py --model llama-3.2-1b", file=sys.stderr)
        return 2
    lock = acquire_lock()
    if lock is None:
        print("다른 실험이 돌고 있다 (logs/exp-run.lock)", file=sys.stderr)
        return 3
    summary = run_job({"model": args.model, "quant": args.quant, "promptset": args.promptset,
                       "json_constraint": args.json_constraint, "thinking": args.thinking})
    print(json.dumps({k: summary[k] for k in ("run_id", "headline", "complete", "aborted")}, ensure_ascii=False))
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
