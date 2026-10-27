#!/usr/bin/env bash
# Hugo(extended)와 Caddy를 GitHub 릴리스 arm64 바이너리로 ~/.local/bin에 설치한다.
# sudo 불필요. 버전을 올리려면 아래 값만 바꾸고 다시 실행한다.
# 받은 파일은 릴리스의 checksums 파일로 검증한다.
set -euo pipefail

HUGO_VERSION="${HUGO_VERSION:-0.167.0}"
CADDY_VERSION="${CADDY_VERSION:-2.11.7}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"

work="$(mktemp -d /tmp/site-tools.XXXXXX)"   # /tmp는 RAM이라 SD카드 쓰기를 줄인다
trap 'rm -rf "$work"' EXIT
mkdir -p "$BIN_DIR"
cd "$work"

# Hugo extended
hugo_tar="hugo_extended_${HUGO_VERSION}_linux-arm64.tar.gz"
hugo_base="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}"
curl -fsSLO "$hugo_base/$hugo_tar"
curl -fsSL "$hugo_base/hugo_${HUGO_VERSION}_checksums.txt" | grep " ${hugo_tar}\$" | sha256sum -c -
tar -xzf "$hugo_tar" hugo
install -m 755 hugo "$BIN_DIR/hugo"

# Caddy
caddy_tar="caddy_${CADDY_VERSION}_linux_arm64.tar.gz"
caddy_base="https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}"
curl -fsSLO "$caddy_base/$caddy_tar"
curl -fsSL "$caddy_base/caddy_${CADDY_VERSION}_checksums.txt" | grep " ${caddy_tar}\$" | sha512sum -c -
tar -xzf "$caddy_tar" caddy
install -m 755 caddy "$BIN_DIR/caddy"

"$BIN_DIR/hugo" version
"$BIN_DIR/caddy" version

# 글 링크 미리보기 카드(site/scripts/og-card.py)는 운영 venv가 아니라 시스템 파이썬의 Pillow로 그린다
# (blogops publish.cover_cards). 2026-10-27 이 Pi에는 Debian python3-pil 11.1이 있다. 없으면 글마다 기본 카드가 붙는다
if ! /usr/bin/python3 -c "import PIL" 2>/dev/null; then
  echo "주의: 시스템 파이썬에 Pillow가 없다. 설치: sudo apt install python3-pil" >&2
fi
