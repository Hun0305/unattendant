#!/usr/bin/env bash
# 매장 폴더를 만든다 (docs/blogops.md 7절). Huninn이 상주하며 쓰는 운영 레포·사이트 레포 체크아웃이다.
# 작업실(~/unattendant)을 복사하지 않고 GitHub에서 따로 clone한다. 매장에는 GitHub main에 올라간 것만 들어온다.
# 여러 번 돌려도 된다(이미 있는 것은 건너뛴다). sudo 불필요.
# 하지 않는 것: Caddy 경로 변경(sudo), systemd 타이머, 작업실 .env 삭제,
#   Huninn용 Claude Code 설정 설치(ops/install-huninn-config.sh, 작업실·매장이 같은 ~/.config/huninn/claude를 쓴다)
set -euo pipefail

LIVE="${LIVE:-$HOME/unattendant-live}"
OPS_REMOTE="git@github-unattendant-ops:Hun0305/unattendant.git"
SITE_REMOTE="git@github-unattendant-site:Hun0305/unattendant.dev.git"
HUNINN_HOME="${HUNINN_HOME:-$HOME/.config/huninn}"
ENV_SRC="${ENV_SRC:-$HOME/unattendant/.env}"            # 비밀값 파일이 아직 없을 때 처음 한 번 복사할 원본
WORK_VENV="${WORK_VENV:-$HOME/unattendant/agent/.venv}"  # 있으면 이 가상환경과 같은 패키지 버전으로 맞춘다

echo "1) clone: $LIVE"
[ -d "$LIVE/.git" ] || git clone -q "$OPS_REMOTE" "$LIVE"
[ -d "$LIVE/site/.git" ] || git clone -q "$SITE_REMOTE" "$LIVE/site"
git -C "$LIVE" log -1 --format='   운영 레포   %h %s'
git -C "$LIVE/site" log -1 --format='   사이트 레포 %h %s'

echo "2) pre-commit 훅: 매장의 ops/githooks (Huninn의 커밋도 비밀키 검사를 받는다)"
for repo in "$LIVE" "$LIVE/site"; do
  git -C "$repo" config core.hooksPath "$LIVE/ops/githooks"
done
command -v gitleaks >/dev/null || [ -x "$HOME/.local/bin/gitleaks" ] \
  || { echo "gitleaks가 없다. ops/install-gitleaks.sh를 먼저 돌린다" >&2; exit 1; }

echo "3) Python 가상환경: $LIVE/agent/.venv"
[ -x "$LIVE/agent/.venv/bin/python" ] || python3 -m venv "$LIVE/agent/.venv"
constraints=()
if [ -x "$WORK_VENV/bin/pip" ]; then
  pins="$(mktemp /tmp/huninn-pins.XXXXXX)"
  trap 'rm -f "$pins"' EXIT
  { "$WORK_VENV/bin/pip" freeze --exclude-editable | grep -v '^blogops' || true; } > "$pins"
  constraints=(-c "$pins")
  echo "   작업실 가상환경과 같은 버전으로 맞춘다 ($(wc -l < "$pins")개)"
fi
"$LIVE/agent/.venv/bin/pip" install -q -e "$LIVE/agent" "${constraints[@]}"
"$LIVE/agent/.venv/bin/python" -c \
  'import blogops, importlib.metadata as m; print("   blogops", blogops.__file__); print("   mcp", m.version("mcp"))'

echo "4) 비밀값: $HUNINN_HOME/huninn.env (600)"
install -d -m 700 "$HUNINN_HOME"
if [ -f "$HUNINN_HOME/huninn.env" ]; then
  chmod 600 "$HUNINN_HOME/huninn.env"
  echo "   이미 있다. 그대로 둔다"
else
  install -m 600 "$ENV_SRC" "$HUNINN_HOME/huninn.env"
  echo "   $ENV_SRC 에서 복사했다"
fi

echo "5) 사이트 빌드: $LIVE/site/public"
hugo_bin="$(command -v hugo || echo "$HOME/.local/bin/hugo")"
"$hugo_bin" --source "$LIVE/site" --gc --minify --cleanDestinationDir --quiet
echo "   한국어 글 $(find "$LIVE/site/public/posts" -mindepth 2 -name index.html -not -path '*/page/*' 2>/dev/null | wc -l)편"

echo "완료. Caddy가 매장 사이트를 서빙하게 하려면 ops/caddy/Caddyfile의 root를 바꾸고 재시작한다(sudo)."
