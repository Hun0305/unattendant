"""하루 사이클 실행 (docs/blogops.md 1절). ops/huninn/run-cycle.sh가 부른다.

claude -p를 blogops 툴만 쥐여 한 번 돌리고, 결과를 logs/cycles.jsonl에 남긴다.
- 지시: ops/huninn/prompt.md를 시스템 프롬프트로 쓴다 (Claude Code 기본 프롬프트 대신)
- 툴: ops/huninn/mcp.json을 채워 임시 파일로 넘긴다. BLOGOPS_로 시작하는 환경변수는 서버에도 넘긴다
- 비밀값: 구독 토큰(CLAUDE_CODE_OAUTH_TOKEN)만 꺼내 claude에 넘긴다. 디스코드 토큰은 서버가 직접 읽는다
- 작업 폴더: 레포 밖(~/.config/huninn/work)에서 돌려 레포의 CLAUDE.md를 읽지 않게 한다
- 실패(종료 코드, is_error, 시간 초과)는 #긴급(멘션)으로, 툴 호출 상한에 걸리면 #긴급으로 알린다
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import string
import subprocess
import sys
import tempfile
from pathlib import Path

from . import env, notify
from .config import Config, find_tool
from .env import EnvError
from .notify import NotifyError

# 지정하지 않으면 Pro 기본 모델이 쓰이고, 기본 모델은 바뀔 수 있다 (ops/README.md). HUNINN_MODEL로 바꾼다
DEFAULT_MODEL = "claude-sonnet-5-5"
TIMEOUT = 25 * 60  # systemd 제한(30분)보다 먼저 멈춰서 기록과 알림을 남긴다
RESULT_MAX = 2000
WEEKDAYS = "월화수목금토일"


class CycleError(Exception):
    pass


def huninn_home() -> Path:
    return Path(os.environ.get("HUNINN_HOME") or Path.home() / ".config" / "huninn")


def _fill(value, mapping: dict):
    if isinstance(value, str):
        return string.Template(value).substitute(mapping)
    if isinstance(value, list):
        return [_fill(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, mapping) for k, v in value.items()}
    return value


def mcp_config(config: Config, cycle_id: str) -> dict:
    template = json.loads((config.root / "ops" / "huninn" / "mcp.json").read_text(encoding="utf-8"))
    data = _fill(template, {"BLOGOPS_ROOT": str(config.root)})
    server_env = data["mcpServers"]["blogops"].setdefault("env", {})
    # 시험 실행 옵션(BLOGOPS_NO_PUBLISH, BLOGOPS_SITE_DIR 등)이 서버까지 가야 한다
    server_env.update({k: v for k, v in os.environ.items() if k.startswith("BLOGOPS_")})
    server_env["BLOGOPS_CYCLE_ID"] = cycle_id
    return data


def command(config: Config, mcp_path: Path, model: str) -> list[str]:
    """ops/README.md "실행 옵션". 사용자 메시지는 stdin으로 넘긴다(--tools, --mcp-config가 값을 여러 개 받는다)."""
    binary = os.environ.get("HUNINN_CLAUDE") or find_tool("claude")
    if not binary:
        raise CycleError("claude가 없다")
    prompt = (config.root / "ops" / "huninn" / "prompt.md").read_text(encoding="utf-8")
    return [binary, "-p",
            "--model", model,
            "--system-prompt", prompt,
            "--tools", "",
            "--mcp-config", str(mcp_path), "--strict-mcp-config",
            "--setting-sources", "user",
            "--permission-mode", "dontAsk",
            "--no-session-persistence",
            "--output-format", "json"]


def claude_env(config: Config) -> dict:
    # 사람 세션의 Claude Code 변수와 API 키는 넘기지 않는다 (API 키가 있으면 구독 대신 쓰일 수 있다)
    base = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC_"))}
    base["CLAUDE_CODE_OAUTH_TOKEN"] = env.get(config, "CLAUDE_CODE_OAUTH_TOKEN")
    base["CLAUDE_CONFIG_DIR"] = str(huninn_home() / "claude")  # 셸에 사람용 값이 있어도 쓰지 않는다
    return base


def user_message(cycle_id: str, now) -> str:
    lines = [f"사이클을 시작한다. 지금은 {now:%Y-%m-%d}({WEEKDAYS[now.weekday()]}) {now:%H:%M} KST이고, "
             f"사이클 ID는 {cycle_id}다. 시스템 프롬프트의 하루 순서를 따른다."]
    if os.environ.get("BLOGOPS_NO_PUBLISH"):
        lines.append("이번은 시험 실행이다. publish_post는 거부되므로 부르지 않는다. 나머지는 평소대로 한다.")
    return "\n".join(lines)


def _run(cmd: list[str], stdin: str, cwd: Path, env_vars: dict, timeout: float) -> tuple[int, str, str, bool]:
    proc = subprocess.Popen(cmd, cwd=cwd, env=env_vars, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(stdin, timeout=timeout)
        return proc.returncode, out, err, False
    except subprocess.TimeoutExpired:
        for sig, wait in ((signal.SIGTERM, 15), (signal.SIGKILL, None)):  # MCP 서버까지 같이 끝낸다
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
            try:
                out, err = proc.communicate(timeout=wait)
                break
            except subprocess.TimeoutExpired:
                continue
        return proc.returncode, out, err, True


def summarize(stdout: str) -> dict:
    """claude -p --output-format json 결과에서 기록할 것만 고른다."""
    try:
        result = json.loads(stdout)
    except ValueError:
        result = None
    if not isinstance(result, dict):
        return {"claude_error": True, "output": stdout.strip()[-RESULT_MAX:]}
    return {"subtype": result.get("subtype"),
            "claude_error": bool(result.get("is_error")),
            "num_turns": result.get("num_turns"),
            "duration_api_ms": result.get("duration_api_ms"),
            "total_cost_usd": result.get("total_cost_usd"),
            "model_usage": result.get("modelUsage") or {},
            "permission_denials": len(result.get("permission_denials") or []),
            "result": (result.get("result") or "")[:RESULT_MAX]}


def tool_stats(config: Config, cycle_id: str, days: set[str]) -> dict:
    """서버가 남긴 logs/YYYY-MM-DD.jsonl에서 이 사이클의 툴 호출을 센다."""
    calls, errors, limit_hit, tools = 0, 0, False, {}
    for day in sorted(days):
        path = config.logs_dir / f"{day}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("cycle") != cycle_id:
                continue
            if rec.get("event") == "tool_call":
                calls += 1
                errors += not rec.get("ok")
                tools[rec["tool"]] = tools.get(rec["tool"], 0) + 1
            elif rec.get("event") == "tool_limit":
                limit_hit = True
    return {"tool_calls": calls, "tool_errors": errors, "tool_limit_hit": limit_hit, "tools": tools}


def _alert(config: Config, record: dict, transport) -> None:
    if record["is_error"]:
        if record.get("error"):
            reason = record["error"]
        elif record.get("timed_out"):
            reason = "시간 제한 안에 끝나지 않아 멈췄다"
        else:
            detail = (record.get("result") or record.get("output") or "").strip()[:300]
            reason = f"claude 종료 코드 {record.get('exit_code')}, {record.get('subtype') or '결과 없음'}" + \
                     (f": {detail}" if detail else "")
        level, message = "critical", f"Huninn 사이클이 실패했다 ({record['cycle']}). {reason}"
    elif record.get("tool_limit_hit"):
        level, message = "warn", (f"툴 호출 상한({config.max_tool_calls_per_cycle}회)에 걸려 사이클이 중간에 끝났다 "
                                  f"({record['cycle']})")
    else:
        return
    try:
        notify.notify_human(config, level, message, transport=transport)
    except (NotifyError, EnvError) as e:
        record["notify_error"] = str(e)


def _append(config: Config, record: dict) -> None:
    with open(config.logs_dir / "cycles.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(config: Config, *, model: str | None = None, timeout: float = TIMEOUT, transport=None) -> dict:
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    with open(config.logs_dir / ".cycle.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CycleError("다른 사이클이 돌고 있다") from None
        return _run_cycle(config, model or os.environ.get("HUNINN_MODEL") or DEFAULT_MODEL, timeout, transport)


def _run_cycle(config: Config, model: str, timeout: float, transport) -> dict:
    started = config.now()
    cycle_id = f"cycle-{started:%Y%m%dT%H%M%S}"
    record = {"cycle": cycle_id, "started": started.isoformat(timespec="seconds"), "model": model,
              "dry_run": bool(os.environ.get("BLOGOPS_NO_PUBLISH")), "estimate": True}
    try:
        workdir = huninn_home() / "work"
        workdir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="huninn-cycle-") as tmp:
            mcp_path = Path(tmp) / "mcp.json"
            mcp_path.write_text(json.dumps(mcp_config(config, cycle_id), ensure_ascii=False), encoding="utf-8")
            code, out, err, timed_out = _run(command(config, mcp_path, model), user_message(cycle_id, started),
                                             workdir, claude_env(config), timeout)
        record.update(exit_code=code, timed_out=timed_out, **summarize(out))
        if code != 0 or timed_out or record["claude_error"]:
            record["stderr"] = err.strip()[-1000:]
    except (CycleError, EnvError, OSError) as e:
        record["error"] = str(e)
    ended = config.now()
    record.update(tool_stats(config, cycle_id, {started.date().isoformat(), ended.date().isoformat()}))
    record["is_error"] = bool(record.get("error") or record.get("timed_out") or record.get("exit_code")
                              or record.get("claude_error"))
    record = {"ts": ended.isoformat(timespec="seconds"), **record,
              "seconds": round((ended - started).total_seconds())}
    _alert(config, record, transport)
    _append(config, record)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run-cycle", description="Huninn 하루 사이클을 한 번 돌린다")
    parser.add_argument("--model", help=f"모델 (기본: HUNINN_MODEL, 없으면 {DEFAULT_MODEL})")
    parser.add_argument("--show", action="store_true", help="실행할 명령과 MCP 설정만 보여 주고 돌리지 않는다")
    args = parser.parse_args(argv)
    config = Config.from_env()
    model = args.model or os.environ.get("HUNINN_MODEL") or DEFAULT_MODEL

    if args.show:
        cmd = command(config, Path("<임시 폴더>/mcp.json"), model)
        cmd[cmd.index("--system-prompt") + 1] = f"<ops/huninn/prompt.md {len(cmd[cmd.index('--system-prompt') + 1])}자>"
        print("작업 폴더:", huninn_home() / "work")
        print("명령:", " ".join(json.dumps(c, ensure_ascii=False) if not c or " " in c else c for c in cmd))
        print("MCP 설정:", json.dumps(mcp_config(config, "cycle-<시각>"), ensure_ascii=False, indent=2))
        return 0

    try:
        record = run(config, model=args.model)
    except CycleError as e:
        print(f"사이클을 시작하지 않았다: {e}", file=sys.stderr)
        return 2
    cost = record.get("total_cost_usd")
    print(f"{record['cycle']} {'실패' if record['is_error'] else '완료'}: {record['seconds']}초, "
          f"툴 {record['tool_calls']}회(오류 {record['tool_errors']}), 추정 비용 "
          f"{'-' if cost is None else f'${cost:.4f}'}")
    for line in (record.get("error"), record.get("result"), record.get("notify_error")):
        if line:
            print(line)
    return 1 if record["is_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
