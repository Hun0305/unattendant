#!/usr/bin/env bash
# log2ram 설치: /var/log를 RAM(tmpfs)에 올리고, 하루 한 번과 종료할 때만 SD카드에 기록한다.
# Debian trixie 공식 패키지(log2ram 1.7.2+ds-1)를 쓰고 설정은 기본값 그대로 둔다
#   SIZE=128M (상한일 뿐, 실제로는 쓰는 만큼만 RAM을 쓴다. 2026-10-06 /var/log는 2.8MB)
#   JOURNALD_AWARE=true, LOG_DISK_SIZE=256M
# 적용하려면 재부팅이 필요하다. sudo 필요.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y log2ram
systemctl is-enabled log2ram.service log2ram-daily.timer

echo
echo "설치 완료. 재부팅 후 아래로 확인한다:"
echo "  findmnt /var/log                 # FSTYPE이 tmpfs, SOURCE가 log2ram이면 적용된 것"
echo "  systemctl status log2ram --no-pager"
