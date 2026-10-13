#!/usr/bin/env bash
# 인바운드 가드 설치 (2026-10-14): SSH·FTP·MQTT·rpcbind를 집 안(같은 네트워크)과 Tailscale에서만 받는다.
# 규칙 원본은 ops/firewall/unattendant-guard.nft.in, 부팅 유닛은 ops/systemd/unattendant-firewall.service.
# 설명과 순서: ops/README.md "인바운드 가드 (sudo)"
#
#   ops/install-firewall.sh render     설치될 규칙을 보여 준다 (sudo 불필요)
#   sudo ops/install-firewall.sh apply    규칙을 적용하고, 10분 뒤 자동으로 되돌리는 타이머를 같이 건다
#   sudo ops/install-firewall.sh confirm  새 접속이 되는 것을 확인한 뒤: 되돌리기를 취소하고 부팅 때도 켜지게 한다
#   sudo ops/install-firewall.sh status   규칙, 막은 횟수, 같은 대역에서 접속한 주소
#   sudo ops/install-firewall.sh remove   규칙을 지우고 부팅 때 켜지지 않게 한다
#
# 원격에서 방화벽을 바꾸다 잠기지 않게 apply는 confirm 전까지 임시다. 확인하지 않으면 10분 뒤 규칙이 지워진다.
# eth0의 IPv4 대역이 바뀌면(DHCP) apply와 confirm을 다시 한다. 시험(가상 네트워크, sudo 불필요): ops/test-firewall.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$HERE/firewall/unattendant-guard.nft.in"
UNIT_SRC="$HERE/systemd/unattendant-firewall.service"
RULES=/etc/nftables.d/unattendant-guard.nft
UNIT=/etc/systemd/system/unattendant-firewall.service
TABLE="inet unattendant_guard"
ROLLBACK=unattendant-guard-rollback
ROLLBACK_AFTER=10min
IFACE="${IFACE:-eth0}"

need_root() {
  [ "$(id -u)" -eq 0 ] || { echo "sudo로 실행한다: sudo $0 $1" >&2; exit 1; }
}

lan4() {  # eth0의 IPv4 대역. 시험에서는 LAN4로 정한다
  if [ -n "${LAN4:-}" ]; then echo "$LAN4"; return; fi
  local addr
  addr="$(ip -4 -o addr show dev "$IFACE" scope global | awk '{print $4}' | head -1)"
  [ -n "$addr" ] || { echo "$IFACE에 IPv4 주소가 없다" >&2; exit 1; }
  python3 -c 'import ipaddress, sys; print(ipaddress.ip_interface(sys.argv[1]).network)' "$addr"
}

render() {
  local net
  net="$(lan4)"
  sed "s|@LAN4@|$net|" "$TEMPLATE"
}

stop_rollback() {
  systemctl stop "$ROLLBACK.timer" "$ROLLBACK.service" 2>/dev/null || true
  systemctl reset-failed "$ROLLBACK.timer" "$ROLLBACK.service" 2>/dev/null || true
}

case "${1:-}" in
  render)
    render
    ;;
  apply)
    need_root apply
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT
    render > "$tmp"
    nft -c -f "$tmp"  # 넣기 전에 문법과 이름을 검사한다
    install -d -m 755 /etc/nftables.d
    install -m 644 "$tmp" "$RULES"
    stop_rollback
    systemd-run --quiet --unit="$ROLLBACK" --on-active="$ROLLBACK_AFTER" --timer-property=AccuracySec=1s \
      /usr/sbin/nft delete table $TABLE
    nft -f "$RULES"
    echo "적용했다 (대역 $(lan4)). 확인하지 않으면 $ROLLBACK_AFTER 뒤 자동으로 지워진다."
    echo
    echo "지금 연결은 끊지 말고, 새 접속이 되는지 본다:"
    echo "  1. 집 안 PC에서 새 터미널로 ssh 접속"
    echo "  2. Tailscale로 ssh 접속 (폰이나 다른 기기)"
    echo "둘 다 되면:   sudo $0 confirm"
    echo "안 되면:      아무것도 하지 않는다 ($ROLLBACK_AFTER 뒤 되돌아간다). 바로 되돌리려면 sudo nft delete table $TABLE"
    ;;
  confirm)
    need_root confirm
    nft list table $TABLE > /dev/null || { echo "규칙이 없다. 이미 되돌아갔으면 apply부터 다시 한다" >&2; exit 1; }
    stop_rollback
    install -m 644 "$UNIT_SRC" "$UNIT"
    systemctl daemon-reload
    systemctl enable --now unattendant-firewall.service
    echo "확정했다. 부팅할 때도 켜진다."
    systemctl --no-pager --lines=0 status unattendant-firewall.service || true
    ;;
  status)
    need_root status
    nft list table $TABLE 2>/dev/null || echo "규칙이 없다"
    echo
    enabled="$(systemctl is-enabled unattendant-firewall.service 2>/dev/null)" || true
    rollback="$(systemctl is-active "$ROLLBACK.timer" 2>/dev/null)" || true
    echo "부팅 유닛: ${enabled:-없음}"
    echo "되돌리기 타이머: ${rollback:-없음}"
    ;;
  remove)
    need_root remove
    stop_rollback
    systemctl disable --now unattendant-firewall.service 2>/dev/null || true
    nft delete table $TABLE 2>/dev/null || true
    rm -f "$UNIT" "$RULES"
    systemctl daemon-reload
    echo "지웠다."
    ;;
  *)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
