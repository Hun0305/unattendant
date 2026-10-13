#!/usr/bin/env bash
# 인바운드 가드 시험 (sudo 불필요). 사용자 네임스페이스 안에 가상 네트워크를 만들어 규칙을 넣고,
# 집 안·인터넷·Tailscale 쪽 가상 기기에서 접속해 본다. Pi의 실제 네트워크와 방화벽은 건드리지 않는다.
#
#   ops/test-firewall.sh
#
# 가상 네트워크 (가운데가 Pi 역할)
#   집 안      lan0 10.9.0.2     ── veth-lan   10.9.0.1/24    (같은 대역 → 허용)
#   인터넷     wan0 203.0.113.2  ── veth-wan   203.0.113.1/24 (대역 밖 → 가드 포트 차단)
#   Tailscale  ts0  100.64.0.2   ── tailscale0 100.64.0.1/24  (Tailscale 인터페이스 → 허용)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
if [ "${1:-}" != "--inside" ]; then
  exec unshare --user --map-root-user --net "$0" --inside
fi

WORK="$(mktemp -d)"
PIDS=()
cleanup() { kill "${PIDS[@]}" 2>/dev/null || true; rm -rf "$WORK"; }
trap cleanup EXIT

# ── 가상 네트워크 ────────────────────────────────────
ip link set lo up
for name in lan wan ts; do
  unshare --net sleep 600 &
  PIDS+=($!)
  declare "PID_$name=$!"
done
in_ns() { local pid=$1; shift; nsenter --target "$pid" --net "$@"; }

ip link add veth-lan type veth peer name lan0 netns "$PID_lan"
ip link add veth-wan type veth peer name wan0 netns "$PID_wan"
ip link add tailscale0 type veth peer name ts0 netns "$PID_ts"
ip addr add 10.9.0.1/24 dev veth-lan && ip link set veth-lan up
ip addr add 203.0.113.1/24 dev veth-wan && ip link set veth-wan up
ip addr add 100.64.0.1/24 dev tailscale0 && ip link set tailscale0 up
in_ns "$PID_lan" sh -c 'ip link set lo up; ip addr add 10.9.0.2/24 dev lan0; ip link set lan0 up'
in_ns "$PID_wan" sh -c 'ip link set lo up; ip addr add 203.0.113.2/24 dev wan0; ip link set wan0 up'
in_ns "$PID_ts" sh -c 'ip link set lo up; ip addr add 100.64.0.2/24 dev ts0; ip link set ts0 up'

wait_dad() {  # 링크 로컬 주소가 쓸 수 있게 될 때까지 (최대 10초)
  for _ in $(seq 50); do
    if [ -z "$(ip -6 addr show tentative)" ] && [ -z "$(in_ns "$PID_wan" ip -6 addr show tentative)" ]; then
      return 0
    fi
    sleep 0.2
  done
  echo "링크 로컬 주소가 준비되지 않았다" >&2
  exit 1
}
wait_dad
PI_LL="$(ip -6 -o addr show dev veth-wan scope link | awk '{print $4}' | cut -d/ -f1)"

# ── 서버와 클라이언트 ────────────────────────────────
cat > "$WORK/serve.py" <<'EOF'
import selectors, socket
sel = selectors.DefaultSelector()
for port in (21, 22, 111, 1883, 8080):
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("::", port)); s.listen(); s.setblocking(False)
    sel.register(s, selectors.EVENT_READ, "tcp")
u = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
u.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
u.bind(("::", 111)); sel.register(u, selectors.EVENT_READ, "udp")
print("ready", flush=True)
while True:
    for key, _ in sel.select():
        if key.data == "tcp":
            conn, _ = key.fileobj.accept(); conn.sendall(b"ok"); conn.close()
        else:
            data, addr = key.fileobj.recvfrom(64); key.fileobj.sendto(b"ok", addr)
EOF
cat > "$WORK/probe.py" <<'EOF'
import socket, sys
proto, host, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
family = socket.AF_INET6 if ":" in host else socket.AF_INET
addr = socket.getaddrinfo(host, port, family)[0][4]
s = socket.socket(family, socket.SOCK_STREAM if proto == "tcp" else socket.SOCK_DGRAM)
s.settimeout(2)
try:
    if proto == "tcp":
        s.connect(addr); s.recv(8)
    else:
        s.sendto(b"hi", addr); s.recvfrom(8)
    print("open")
except socket.timeout:
    print("blocked")
except ConnectionRefusedError:
    print("refused")
EOF
python3 -I "$WORK/serve.py" > "$WORK/serve.log" &
PIDS+=($!)
for _ in $(seq 50); do grep -q ready "$WORK/serve.log" 2>/dev/null && break; sleep 0.1; done

FAILED=0
check() {  # check <설명> <기대> <ns pid 또는 self> <tcp|udp> <주소> <포트>
  local desc=$1 want=$2 who=$3 proto=$4 host=$5 port=$6 got
  if [ "$who" = self ]; then
    got="$(python3 -I "$WORK/probe.py" "$proto" "$host" "$port")"
  else
    got="$(in_ns "$who" python3 -I "$WORK/probe.py" "$proto" "$host" "$port")"
  fi
  if [ "$got" = "$want" ]; then
    printf '  통과  %-46s %s\n' "$desc" "$got"
  else
    printf '  실패  %-46s 기대 %s, 결과 %s\n' "$desc" "$want" "$got"
    FAILED=$((FAILED + 1))
  fi
}

echo "규칙 넣기 전 (시험이 차단을 알아보는지 확인)"
check "인터넷 → SSH" open "$PID_wan" tcp 203.0.113.1 22

LAN4=10.9.0.0/24 "$HERE/install-firewall.sh" render > "$WORK/guard.nft"
nft -c -f "$WORK/guard.nft"
nft -f "$WORK/guard.nft"

echo "규칙 넣은 뒤"
for port in 22 21 111 1883; do
  check "집 안 → tcp $port" open "$PID_lan" tcp 10.9.0.1 "$port"
done
check "집 안 → udp 111" open "$PID_lan" udp 10.9.0.1 111
for port in 22 21 111 1883; do
  check "인터넷 → tcp $port" blocked "$PID_wan" tcp 203.0.113.1 "$port"
done
check "인터넷 → udp 111" blocked "$PID_wan" udp 203.0.113.1 111
check "인터넷 → tcp 8080 (가드 밖 포트는 그대로)" open "$PID_wan" tcp 203.0.113.1 8080
check "Tailscale → tcp 22" open "$PID_ts" tcp 100.64.0.1 22
check "Tailscale → tcp 1883" open "$PID_ts" tcp 100.64.0.1 1883
check "링크 로컬 IPv6 → tcp 22 (집 안 PC가 쓰는 길)" open "$PID_wan" tcp "$PI_LL%wan0" 22
check "Pi 자신(lo) → tcp 22" open self tcp 127.0.0.1 22

echo "기록"
nft list set inet unattendant_guard lan4_seen | grep -q "10.9.0.2" \
  && echo "  통과  같은 대역에서 접속한 주소가 lan4_seen에 남는다" \
  || { echo "  실패  lan4_seen에 10.9.0.2가 없다"; FAILED=$((FAILED + 1)); }
drops="$(nft list chain inet unattendant_guard input | grep -c 'counter packets [1-9]' || true)"
[ "$drops" -eq 2 ] \
  && echo "  통과  차단 규칙 두 개(tcp, udp)의 카운터가 올라갔다" \
  || { echo "  실패  차단 카운터가 기대와 다르다 ($drops)"; FAILED=$((FAILED + 1)); }

echo "다시 넣기 (apply를 두 번 해도 되는지)"
nft -f "$WORK/guard.nft"
[ "$(nft list tables | grep -c unattendant_guard)" -eq 1 ] \
  && echo "  통과  표가 하나만 있다" \
  || { echo "  실패  표가 겹쳤다"; FAILED=$((FAILED + 1)); }

echo
if [ "$FAILED" -eq 0 ]; then echo "모두 통과"; else echo "실패 $FAILED건"; exit 1; fi
