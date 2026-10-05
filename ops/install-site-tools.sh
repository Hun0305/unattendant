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
