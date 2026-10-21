#!/usr/bin/env bash
# 밤 실험 타이머를 사용자 매니저에 설치한다 (sudo 불필요). 재부팅해도 남는다.
# 원본은 ops/systemd/user/에 두고 ~/.config/systemd/user/로 복사한다. 설명은 experiments/README.md "실행"
#   ops/install-exp-timer.sh            설치하고 타이머를 켠다
#   ops/install-exp-timer.sh --remove   타이머를 끄고 유닛을 지운다
# 사용자 매니저는 tty1 자동 로그인 세션이 붙잡고 있다(Linger=no). 그 세션이 없으면 타이머도 돌지 않는다
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNITS=(exp-night.service exp-night.timer)

if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now exp-night.timer 2>/dev/null || true
  for unit in "${UNITS[@]}"; do rm -f "$DEST/$unit"; done
  systemctl --user daemon-reload
  echo "지웠다: ${UNITS[*]}"
  exit 0
fi

for unit in "${UNITS[@]}"; do
  systemd-analyze --user verify "$ROOT/ops/systemd/user/$unit"   # 문법 확인 (설치 전)
done
install -d "$DEST"
for unit in "${UNITS[@]}"; do
  if [ -f "$DEST/$unit" ] && ! cmp -s "$ROOT/ops/systemd/user/$unit" "$DEST/$unit"; then
    echo "바뀌는 내용 ($unit):"; diff -u "$DEST/$unit" "$ROOT/ops/systemd/user/$unit" || true
  fi
  install -m 644 "$ROOT/ops/systemd/user/$unit" "$DEST/$unit"
done
systemctl --user daemon-reload
systemctl --user enable --now exp-night.timer
systemctl --user list-timers exp-night.timer --no-pager
