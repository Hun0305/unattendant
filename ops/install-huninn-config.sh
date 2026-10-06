#!/usr/bin/env bash
# Huninn 전용 Claude Code 설정을 설치한다.
# 원본은 레포(ops/huninn/settings.json, 공개)에 두고, 실제로 읽히는 위치(레포 밖)로 복사한다.
# 로그인 정보·대화 기록은 이 폴더에만 생기고 레포로 돌아오지 않는다. sudo 불필요.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/ops/huninn/settings.json"
DEST_DIR="${HUNINN_CLAUDE_DIR:-$HOME/.config/huninn/claude}"

python3 -m json.tool "$SRC" >/dev/null          # JSON 문법 확인
install -d -m 700 "$(dirname "$DEST_DIR")" "$DEST_DIR"
if [ -f "$DEST_DIR/settings.json" ] && ! cmp -s "$SRC" "$DEST_DIR/settings.json"; then
  echo "바뀌는 내용:"; diff -u "$DEST_DIR/settings.json" "$SRC" || true
fi
install -m 600 "$SRC" "$DEST_DIR/settings.json"
echo "설치: $DEST_DIR/settings.json"
