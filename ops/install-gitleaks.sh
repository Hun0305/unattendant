#!/usr/bin/env bash
# gitleaks(비밀키 스캐너)를 GitHub 릴리스 arm64 바이너리로 ~/.local/bin에 설치하고,
# 두 레포(~/unattendant, ~/unattendant/site)의 pre-commit 훅을 ops/githooks로 연결한다.
# sudo 불필요. 버전을 올리려면 아래 값만 바꾸고 다시 실행한다.
set -euo pipefail

GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.30.1}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

work="$(mktemp -d /tmp/gitleaks.XXXXXX)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$BIN_DIR"
cd "$work"

tarball="gitleaks_${GITLEAKS_VERSION}_linux_arm64.tar.gz"
base="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
curl -fsSLO "$base/$tarball"
curl -fsSL "$base/gitleaks_${GITLEAKS_VERSION}_checksums.txt" | grep " ${tarball}\$" | sha256sum -c -
tar -xzf "$tarball" gitleaks
install -m 755 gitleaks "$BIN_DIR/gitleaks"
"$BIN_DIR/gitleaks" version

# 훅 연결 (.git/hooks 대신 레포에 있는 ops/githooks를 쓴다)
git -C "$ROOT" config core.hooksPath "$ROOT/ops/githooks"
git -C "$ROOT/site" config core.hooksPath "$ROOT/ops/githooks"
echo "hooksPath: $(git -C "$ROOT" config core.hooksPath)"
