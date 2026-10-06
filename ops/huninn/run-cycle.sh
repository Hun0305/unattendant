#!/usr/bin/env bash
# Huninn 하루 사이클을 한 번 돌린다 (docs/blogops.md 1절). 이 파일이 들어 있는 체크아웃의 state/를 다룬다.
# 하는 일은 agent/blogops/cycle.py에 있다: claude -p 실행, logs/cycles.jsonl 기록, 실패 알림.
#   ops/huninn/run-cycle.sh --show            실행할 명령과 MCP 설정만 본다
#   BLOGOPS_NO_PUBLISH=1 ops/huninn/run-cycle.sh   시험 실행 (발행은 거부된다)
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
export BLOGOPS_ROOT="$ROOT"
exec "$ROOT/agent/.venv/bin/python" -m blogops.cycle "$@"
