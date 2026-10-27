#!/usr/bin/env bash
# 메모리가 모자랄 때 실험이 먼저 죽고 블로그·원격 접속은 남게 OOM 우선순위를 건다 (ops/README.md "OOM 우선순위").
#   SSH, Caddy, 터널: OOMScoreAdjust=-500   /   밤 실험(exp-night, 사용자 유닛): +500 (이미 유닛에 있다)
# 실행: sudo bash ops/install-oom-guard.sh   (매장 ~/unattendant-live에서. 유닛 파일을 그 레포에서 설치한다)
# OOMScoreAdjust는 프로세스를 시작할 때 걸리므로 세 서비스를 다시 시작한다.
#   - sshd를 다시 시작해도 이미 열린 SSH 세션은 끊기지 않는다
#   - Caddy·터널은 다시 시작하는 몇 초 동안 사이트가 끊긴다
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "sudo로 실행한다: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

install -m 644 "$ROOT/ops/systemd/unattendant-caddy.service" /etc/systemd/system/
install -m 644 "$ROOT/ops/systemd/unattendant-tunnel.service" /etc/systemd/system/
install -d /etc/systemd/system/ssh.service.d
install -m 644 "$ROOT/ops/systemd/ssh.service.d/oom.conf" /etc/systemd/system/ssh.service.d/oom.conf
systemctl daemon-reload

sshd -t   # 설정 오류로 sshd가 못 뜨는 일을 막는다
systemctl restart ssh.service
systemctl restart unattendant-caddy.service
systemctl restart unattendant-tunnel.service

for unit in ssh unattendant-caddy unattendant-tunnel; do
  pid="$(systemctl show -p MainPID --value "$unit")"
  echo "$unit: $(systemctl is-active "$unit"), OOMScoreAdjust=$(systemctl show -p OOMScoreAdjust --value "$unit"), oom_score_adj=$(cat /proc/"$pid"/oom_score_adj 2>/dev/null || echo '?')"
done
for _ in $(seq 1 30); do
  curl -fsS -o /dev/null https://unattendant.dev/ && break
  sleep 2
done
curl -sS -o /dev/null -w "https://unattendant.dev/ → %{http_code}\n" https://unattendant.dev/
