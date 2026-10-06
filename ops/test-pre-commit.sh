#!/usr/bin/env bash
# pre-commit 훅(ops/githooks/pre-commit)이 비밀값을 막는지 확인한다.
# 임시 레포를 만들어 경우마다 커밋을 시도하고, 결과와 걸린 시간을 표로 출력한다.
# 가짜 값은 실행할 때 만든다. 이 파일 자체가 스캐너에 걸리지 않도록 패턴을 쪼개서 적었다.
# 사용: ops/test-pre-commit.sh [결과를 저장할 파일]
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/dev/null}"
T="$(mktemp -d /tmp/precommit-test.XXXXXX)"
trap 'rm -rf "$T"' EXIT

git -C "$T" init -q -b main
git -C "$T" config core.hooksPath "$ROOT/ops/githooks"
git -C "$T" config user.name test
git -C "$T" config user.email test@example.invalid

rand() { python3 -c "import random,string,sys;r=random.Random(int(sys.argv[2]));print(''.join(r.choice(sys.argv[3]) for _ in range(int(sys.argv[1]))))" "$@"; }
AN="$(printf '%s%s' 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' '0123456789')"
B='-----BEGIN'; E='-----END'

pass=0; fail=0
run() {  # run <이름> <기대(COMMITTED|BLOCKED)> <파일> <내용>
  local name=$1 want=$2 file=$3 content=$4 got s t
  mkdir -p "$(dirname "$T/$file")"
  printf '%s\n' "$content" > "$T/$file"
  git -C "$T" add -f "$file"
  s=$(date +%s.%N)
  if git -C "$T" commit -q -m "$name" >/dev/null 2>&1; then got=COMMITTED; else got=BLOCKED; fi
  t=$(python3 -c "import sys;print('%.1f' % (float(sys.argv[2])-float(sys.argv[1])))" "$s" "$(date +%s.%N)")
  if [ "$got" = "$want" ]; then ok=OK; pass=$((pass+1)); else ok=FAIL; fail=$((fail+1)); fi
  printf '| %s | %s | %s | %ss | %s |\n' "$name" "$want" "$got" "$t" "$ok" | tee -a "$OUT"
  git -C "$T" rm -q --cached -f "$file" >/dev/null 2>&1; rm -f "$T/$file"
}

printf '| 경우 | 기대 | 결과 | 시간 | 판정 |\n| --- | --- | --- | --- | --- |\n' | tee "$OUT"
run "평범한 문서 (터널 UUID 포함)" COMMITTED ok.md "측정 메모. tokens/s, TunnelID bd749433-fd2f-48ba-b325-ff2115f1a40d"
run "문서 속 키 형식 설명"     COMMITTED fmt.md "API 키는 \`sk-ant-api03-…\`, 구독 토큰은 \`sk-ant-oat01-…\` 형식이다. 예시: sk-ant-oat01-$(printf 'x%.0s' $(seq 32))"
run "Anthropic API 키"     BLOCKED a.py   "KEY = \"sk-ant-api03-$(rand 93 1 "${AN}-_")AA\""
run "Claude Code 구독 토큰"  BLOCKED run.sh "export CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-$(rand 95 9 "${AN}-_")AA"
run "구독 토큰 (로그에 섞임)"  BLOCKED out.txt "request failed: 401 for sk-ant-oat01-$(rand 95 10 "${AN}-_")AA, retrying"
run "디스코드 봇 토큰"       BLOCKED b.py   "TOKEN = \"MTI4NzY1NDMyMTA5ODc2NTQzMg.GaBcDe.$(rand 38 2 "$AN")\""
run "디스코드 웹훅 URL"      BLOCKED h.py   "URL = \"https://discord.com/api/webhooks/1287654321098765432/$(rand 68 3 "$AN")\""
run "GitHub PAT"           BLOCKED g.py   "T = \"gh""p_$(rand 36 4 "$AN")\""
run "터널 자격증명 json"     BLOCKED c.json "{\"AccountTag\":\"$(rand 32 5 0123456789abcdef)\",\"Tunnel""Secret\":\"$(rand 40 6 "$AN")=\",\"TunnelID\":\"bd749433-fd2f-48ba-b325-ff2115f1a40d\"}"
run "cloudflared cert.pem" BLOCKED d.txt  "$B ARGO TUNNEL TOKEN-----"$'\n'"$(rand 64 7 "$AN")"$'\n'"$E ARGO TUNNEL TOKEN-----"
run "SSH 개인 키"           BLOCKED e.txt  "$B OPENSSH PRIVATE KEY-----"$'\n'"$(rand 70 8 "$AN")"$'\n'"$E OPENSSH PRIVATE KEY-----"
run ".env 파일"            BLOCKED .env   "FOO=bar"
run "logs/ 아래 파일"        BLOCKED logs/x.jsonl '{"ok":true}'
run "미발행 초안"            BLOCKED state/drafts/x.md '초안'
run "승인 상태"              BLOCKED state/approvals/x.json '{"approved":false}'

echo "통과 $pass / 실패 $fail" | tee -a "$OUT"
[ "$fail" -eq 0 ]
