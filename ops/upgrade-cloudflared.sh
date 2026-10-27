#!/usr/bin/env bash
# cloudflared를 GitHub 릴리스 arm64 .deb로 올리고 터널 서비스를 다시 시작한다.
# 이 Pi의 cloudflared는 apt 저장소 없이 .deb로 설치돼 있어 `apt upgrade`로는 올라가지 않는다.
# 서비스는 --no-autoupdate로 돌아서 저절로 올라가지도 않는다.
#
# 실행: sudo bash ops/upgrade-cloudflared.sh
# 버전을 바꿀 때는 아래 두 값을 함께 바꾼다. 해시는 릴리스 자산의 sha256
# (https://api.github.com/repos/cloudflare/cloudflared/releases/tags/<버전> 의 assets[].digest).
#
# 2026-10-27: Cloudflare 요청 메일(2026-10-26). eMudhra 중간 인증서 8개의 개인키가 약해
# 2026.10.2 이전 cloudflared는 위조 인증서를 믿을 수 있다. 원본이 http://127.0.0.1(8080, 8081)이라
# 메일이 경고한 "HTTPS 원본 인증서가 거부되는" 문제는 해당 없다.
# 재시작하는 동안(보통 수 초) 사이트와 미리보기가 끊긴다. 터널은 하나뿐이다.
set -euo pipefail

VERSION="2026.10.4"
SHA256="d0d08a43521e52ba0707900ebe67314e7ca6f610b88024fe6562a408ab6a0f4d"
SERVICE="unattendant-tunnel.service"

if [[ $EUID -ne 0 ]]; then
  echo "sudo로 실행한다: sudo bash $0" >&2
  exit 1
fi

echo "지금: $(cloudflared --version)"

work="$(mktemp -d /tmp/cloudflared.XXXXXX)"
trap 'rm -rf "$work"' EXIT
deb="$work/cloudflared-linux-arm64.deb"
curl -fsSL -o "$deb" "https://github.com/cloudflare/cloudflared/releases/download/${VERSION}/cloudflared-linux-arm64.deb"
echo "${SHA256}  ${deb}" | sha256sum -c -

dpkg -i "$deb"
systemctl restart "$SERVICE"

# 터널이 다시 붙을 때까지 기다린다 (최대 60초)
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null https://unattendant.dev/; then
    break
  fi
  sleep 2
done

echo "이후: $(cloudflared --version)"
systemctl --no-pager --lines=5 status "$SERVICE" || true
curl -sS -o /dev/null -w "https://unattendant.dev/ → %{http_code}\n" https://unattendant.dev/
