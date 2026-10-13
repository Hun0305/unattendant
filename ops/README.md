# ops

Pi에서 블로그를 띄우는 데 필요한 설정과 설치 기록. 다른 프로젝트(TrueETA 등)의 서비스·포트는 건드리지 않는다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `install-site-tools.sh` | Hugo extended, Caddy를 GitHub 릴리스 arm64 바이너리로 `~/.local/bin`에 설치 (체크섬 검증, sudo 불필요) |
| `caddy/Caddyfile` | `site/public`을 `127.0.0.1:8080`에 서빙. TLS는 Cloudflare가 맡는다. `:8081` 블록은 초안 미리보기(`state/previews`)를 읽기 전용으로 서빙한다 (아래 "초안 미리보기 호스트") |
| `systemd/unattendant-caddy.service` | Caddy 상시 실행 |
| `cloudflared/config.yml` | Named Tunnel `unattendant` ingress (`unattendant.dev` → `127.0.0.1:8080`, `preview.unattendant.dev` → `127.0.0.1:8081`) |
| `systemd/unattendant-tunnel.service` | 터널 상시 실행 |
| `install-log2ram.sh` | log2ram 설치 (Debian 패키지, 기본 설정, sudo, 재부팅 필요) |
| `install-gitleaks.sh` | gitleaks 설치 + 두 레포의 `core.hooksPath`를 `ops/githooks`로 연결 |
| `githooks/pre-commit` | 커밋 직전 검사: 금지 파일(`.env`, `*.pem`, `*.key`, `logs/`, `state/drafts/`, `state/approvals/`, `state/previews/`, SSH 키) + gitleaks 비밀값 패턴 |
| `test-pre-commit.sh` | 임시 레포에서 가짜 비밀값으로 훅 동작 확인 |
| `gitleaks.toml` | gitleaks 규칙. 기본 규칙 중 18개 + 전용 규칙 6개(cloudflared 자격증명·인증서·토큰, 디스코드 봇 토큰·웹훅, Claude Code 구독 토큰을 포함한 Anthropic 자격증명 전반) |
| `huninn/settings.json` | Huninn 전용 Claude Code 설정 원본 (공개). 아래 "Huninn용 Claude Code 설정 폴더" |
| `install-huninn-config.sh` | 위 원본을 `~/.config/huninn/claude/settings.json`(600)으로 복사 |
| `huninn/prompt.md` | Huninn 시스템 프롬프트 (공개): 원칙, 하루 순서, 글쓰기 규칙. 무엇을 쓸지는 `state/strategy.md`가 정한다 |
| `huninn/mcp.json` | blogops MCP 서버 등록. 서버 이름 `blogops`가 settings.json 허용 규칙 `mcp__blogops`와 맞아야 한다 |
| `huninn/run-cycle.sh` | 하루 사이클을 한 번 돌린다 (`agent/blogops/cycle.py`). 아래 "실행 옵션" |
| `huninn/review` | 사람용 승인·반려 명령 ([agent/README.md](../agent/README.md)) |
| `systemd/huninn-cycle.service` | Huninn 사이클 한 번 (매장의 `run-cycle.sh`, 30분 제한, 쓰기 가능한 곳 제한). 아래 "Huninn 타이머" |
| `systemd/huninn-cycle.timer` | 위 서비스를 매일 14:00(KST)에 실행 |
| `systemd/huninn-cycle-now.path` | 운영자가 반려·접기를 하면(`logs/.cycle-request`가 생기면) 위 서비스를 바로 시작한다. 아래 "반려·접기 직후 바로 쓰기" |
| `systemd/huninn-bot.service` | 디스코드 봇 상시 실행: #승인 메시지의 승인·반려·접기 버튼을 받는다. 아래 "Huninn 봇" |

## 사이트 빌드

```bash
cd ~/unattendant/site && hugo --gc --minify --cleanDestinationDir
```

Caddy는 `public/`을 바로 읽으므로 빌드 후 재시작은 필요 없다.

## 서비스 설치 (sudo)

```bash
cd ~/unattendant
sudo install -m 644 ops/systemd/unattendant-caddy.service ops/systemd/unattendant-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now unattendant-caddy
# 터널은 아래 Named Tunnel 준비 후
sudo systemctl enable --now unattendant-tunnel
```

## Named Tunnel 준비 (한 번만)

2026-10-06 확인: 이 Pi에는 Named Tunnel이 없었다. TrueETA는 Quick Tunnel(`trueeta-tunnel.service`, 현재 disabled)만 썼고 `~/.cloudflared/`도 없었다. 그래서 unattendant 전용 Named Tunnel을 새로 만들었다(id `bd749433-fd2f-48ba-b325-ff2115f1a40d`, 2026-10-06).

```bash
cloudflared tunnel login                         # 브라우저에서 unattendant.dev 존 선택 → ~/.cloudflared/cert.pem
cloudflared tunnel create unattendant            # ~/.cloudflared/<UUID>.json 생성 (비밀값, 커밋 금지)
cloudflared tunnel route dns unattendant unattendant.dev
# cloudflared/config.yml의 TUNNEL_UUID를 실제 UUID로 바꾼다
cloudflared --config ~/unattendant/ops/cloudflared/config.yml tunnel ingress validate
```

## GitHub 레포

| 레포 | 공개 | 로컬 | SSH 별칭 | 키 |
| --- | --- | --- | --- | --- |
| 사이트 레포 `Hun0305/unattendant.dev` | 공개 | `~/unattendant/site` | `github-unattendant-site` | `~/.ssh/unattendant_site` |
| 운영 레포 `Hun0305/unattendant` | 공개 (2026-10-06 결정, 전환 전까지 Private) | `~/unattendant` | `github-unattendant-ops` | `~/.ssh/unattendant_ops` |

키는 레포별 deploy key(쓰기 허용)라 각 레포에만 접근한다. 무인 push를 위해 passphrase가 없다. `~/.ssh/config`의 별칭이 키를 고른다.

```
Host github-unattendant-site
  HostName github.com
  User git
  IdentityFile ~/.ssh/unattendant_site
  IdentitiesOnly yes
# github-unattendant-ops도 같은 형식
```

Pi를 새로 세우면 키를 새로 만들어 GitHub 레포 Settings → Deploy keys에 다시 등록한다.

두 레포 모두 공개다. 비공개는 비밀값(`.env`, `~/.cloudflared/`, `~/.ssh/`), 원본 로그(`logs/`), 미발행 초안(`state/drafts/`, `state/approvals/`, 초안 미리보기 빌드 `state/previews/`)뿐이고 `.gitignore`와 pre-commit 훅이 막는다. 자세한 기준은 [architecture.md](../docs/architecture.md)의 저장소 섹션에 있다.

## 비밀키 스캐너 (pre-commit)

두 레포 모두 커밋 직전에 `ops/githooks/pre-commit`이 돈다. 걸리면 커밋이 만들어지지 않는다. 구성, 규칙, 실험 기록은 [docs/pre-commit.md](../docs/pre-commit.md)에 있다.

- 기본 규칙 222개를 다 쓰면 Pi 4에서 검사 한 번에 약 35초가 걸려서, 관련 있는 규칙만 골랐다. 지금은 커밋당 4\~6초.
- 새 서비스 키를 쓰게 되면 gitleaks 기본 config에서 그 서비스 규칙을 찾아 `gitleaks.toml`에 추가한다.
- 오탐이면 그 줄 끝에 `gitleaks:allow` 주석을 단다. `--no-verify`로 건너뛰지 않는다.
- 히스토리 전체 검사: `gitleaks git --redact --config ops/gitleaks.toml .` (site는 경로를 `site`로)
- 확인(2026-10-06): 가짜 Anthropic 키, 디스코드 봇 토큰·웹훅, GitHub PAT, 터널 자격증명 json, cert.pem, SSH 개인 키, `.env` 모두 차단, 평범한 문서는 통과. 기존 히스토리(운영 레포 3커밋, site 1커밋)는 검출 0건. 같은 날 Claude Code 구독 토큰 규칙을 추가해 15개 경우 모두 통과, 히스토리(운영 16커밋, site 5커밋) 검출 0건.

## Huninn용 Claude Code 설정 폴더

Phase 1(C3)에서 Huninn은 `claude -p`로 돈다. 사람이 쓰는 `~/.claude`(모델·권한 설정, claude.ai에서 동기화된 스킬, 플러그인, 로그인 정보, 대화 기록)를 Huninn이 함께 읽지 않도록 전용 폴더를 쓴다.

```bash
ops/install-huninn-config.sh   # 폴더(700) 만들고 레포 원본 settings.json을 복사(600)
```

원본은 레포 `ops/huninn/settings.json`에 두고(공개, 비밀값 없음) 설치 스크립트로 복사한다. 로그인 정보·대화 기록·기억은 레포 밖 이 폴더에만 생긴다. Pi를 새로 세우면 스크립트만 다시 돌리면 된다.

레포 밖에 두는 이유: 이 폴더에 쌓이는 대화 기록은 툴 출력이 그대로 담긴 원본 로그라 비밀값이나 식별자가 섞일 수 있다.

**분리되는 것** (2026-10-06 확인)

| 항목 | 사람용 위치 | Huninn |
| --- | --- | --- |
| 설정 (`settings.json`) | `~/.claude/settings.json` | 이 폴더 안 |
| 로그인 정보, 대화 기록, auto memory | `~/.claude/` | 이 폴더 안 |
| claude.ai 동기화 스킬, 플러그인 | `~/.claude/skills/`, `~/.claude/plugins/` | 이 폴더 안 (지금 비어 있음) |
| 전역 설정 `.claude.json` (개인 MCP 서버, 앱 상태) | `~/.claude.json` | 이 폴더 안. 임시 폴더를 `CLAUDE_CONFIG_DIR`로 주고 `claude mcp list`를 돌리니 `.claude.json`이 그 폴더 안에 생기고 `~/.claude.json`은 바뀌지 않았다 |

**분리되지 않는 것**

- **작업 폴더와 그 상위 폴더의 `CLAUDE.md`**: Huninn이 `~/unattendant` 안에서 돌면 사람 개발용 지시인 `~/unattendant/CLAUDE.md`를 읽는다. 예를 들어 "커밋과 push는 내가 요청했을 때만 한다"는 Huninn이 글을 발행하며 커밋하는 일과 충돌한다. Phase 1 `settings.json`에 `claudeMdExcludes: ["/home/hun/unattendant/CLAUDE.md"]`를 넣거나, 작업 폴더를 레포 밖에 둔다.
- **작업 폴더의 `.claude/settings.json`, `.mcp.json`**: 지금 레포에는 둘 다 없다.
- **관리 설정 `/etc/claude-code/`**: 이 Pi에는 없다. 상위 폴더(`~`, `/home`, `/`)에도 `CLAUDE.md`, `AGENTS.md`가 없다.

### settings.json (2026-10-06 작성)

Claude Code 2.1.289의 공식 설정 스키마(json.schemastore.org/claude-code-settings.json)로 검증했다.

| 설정 | 값 | 이유 |
| --- | --- | --- |
| `permissions.allow` | `mcp__blogops` | Huninn은 blogops MCP 툴로만 시스템을 건드린다 (architecture.md). 발행 같은 gated 툴의 조건 검사는 blogops 서버가 한다 |
| `permissions.deny` | Bash, Read, Edit, Write, NotebookEdit, Glob, Grep, WebFetch, WebSearch, Agent | 셸이 열리면 `publish_post`의 품질 검사·승인을 건너뛰고 직접 커밋할 수 있다. Read도 막아 `.env`를 읽지 못하게 한다. 읽기 전용 도구는 평소 허락 없이 실행되므로 명시적으로 막는다 |
| `permissions.defaultMode` | `dontAsk` | 허용 목록에 없는 툴은 묻지 않고 거부한다 (무인 실행이라 물어볼 사람이 없다) |
| `disableBypassPermissionsMode`, `disableAutoMode` | `disable` | 실행 옵션으로 권한 검사를 끄는 모드를 켤 수 없게 한다 |
| `claudeMdExcludes` | 레포의 `CLAUDE.md` 전부 | 사람 개발 세션용 지시("커밋과 push는 요청했을 때만" 등)를 Huninn이 읽지 않게 한다. Huninn의 지시는 시스템 프롬프트와 `state/strategy.md`로 준다 |
| `autoMemoryEnabled` | `false` | Huninn의 상태는 레포 `state/`에만 둔다. 보이지 않는 기억이 있으면 판단을 추적할 수 없다 |
| `cleanupPeriodDays` | `7` | 실행 옵션으로 대화 기록 저장을 끄지만, 혹시 남은 기록은 7일 뒤 지운다 (최소 1) |
| `includeGitInstructions` | `false` | git은 blogops가 다룬다. Claude Code 기본 git 지시가 필요 없다 |
| `disableAllHooks` | `true` | 훅으로 셸 명령이 실행될 여지를 없앤다. 툴 호출 기록은 blogops가 남긴다 |
| `enableAllProjectMcpServers` | `false` | 레포에 `.mcp.json`이 생겨도 자동으로 붙지 않게 한다 |
| `forceLoginMethod` | `claudeai` | Phase 1은 Pro 구독 토큰으로만 돈다. **Phase 2에 API 키로 바꿀 때 `console`로 고친다** |

### 실행 옵션

settings.json과 두 겹으로 막는다. `huninn/run-cycle.sh`가 이 옵션으로 `claude -p`를 돌린다(코드는 `agent/blogops/cycle.py`). `run-cycle.sh --show`로 실제 명령과 MCP 설정을 볼 수 있다.

```bash
# --model                          모델을 고정한다 (cycle.py의 DEFAULT_MODEL, HUNINN_MODEL로 바꾼다)
# --system-prompt                  Claude Code 기본 프롬프트 대신 huninn/prompt.md를 쓴다
# --tools ""                       기본 도구를 아예 싣지 않는다
# --mcp-config … --strict-mcp-config  blogops MCP만 연결한다 (mcp.json의 경로를 채운 임시 파일)
# --setting-sources user           레포에 .claude/settings.json이 생겨도 무시한다
# --permission-mode dontAsk        허용 목록 밖의 툴은 묻지 않고 거부한다
# --no-session-persistence         대화 기록을 디스크에 남기지 않는다
# --output-format json             total_cost_usd를 logs/cycles.jsonl에 기록한다
# 사용자 메시지(날짜, 요일, 사이클 ID)는 stdin으로 넘긴다
CLAUDE_CONFIG_DIR=~/.config/huninn/claude CLAUDE_CODE_OAUTH_TOKEN=... \
  claude -p --model <모델> --system-prompt "<huninn/prompt.md>" \
  --tools "" \
  --mcp-config <임시 폴더>/mcp.json --strict-mcp-config \
  --setting-sources user \
  --permission-mode dontAsk \
  --no-session-persistence \
  --output-format json
```

`cycle.py`가 옵션 말고 더 지키는 것:

- **작업 폴더**: 레포 밖 `~/.config/huninn/work`에서 돌려, 레포 `CLAUDE.md`를 읽을 일 자체가 없게 한다.
- **환경변수**: `CLAUDE`·`ANTHROPIC_`으로 시작하는 변수(사람 세션 변수, API 키)는 넘기지 않는다. 비밀값 파일에서 구독 토큰만 꺼내 넘기고, `CLAUDE_CONFIG_DIR`은 셸에 다른 값이 있어도 늘 `~/.config/huninn/claude`다. 디스코드 토큰은 MCP 서버가 직접 읽는다.
- **한 번에 하나, 25분 제한**: `logs/.cycle.lock`으로 사이클이 겹치지 않게 하고, 25분이 지나면 claude와 MCP 서버를 함께 끝낸다. systemd 제한(30분)보다 먼저 멈춰서 기록과 알림을 남긴다.
- **기록과 알림**: `logs/cycles.jsonl`에 소요 시간, 턴 수, 툴 호출 수, 추정 비용(`estimate: true`)을 남긴다. 실패하면 #긴급(멘션), 툴 호출 상한에 걸리면 #긴급으로 알린다.

**구독 토큰으로 확인한 것** (2026-10-07)

작업 폴더를 레포(`~/unattendant`)로 두고, 위 옵션 중 `--mcp-config`만 빼고(blogops가 아직 없다) `claude -p`를 한 번 돌렸다. Claude에게 "보이는 지시문의 첫 문장"과 "쓸 수 있는 도구"를 물었다.

| 확인 | 결과 |
| --- | --- |
| 구독 토큰 + 전용 폴더로 인증 | `success`, 2.6초 |
| 레포 `CLAUDE.md`가 빠지는지 | 지시문 `NONE` (`claudeMdExcludes`와 `--setting-sources user` 중 무엇이 막았는지는 나누어 보지 않았다) |
| 기본 도구가 빠지는지 | 도구 `NONE` (`--tools ""`) |
| claude.ai 동기화 스킬 | 이 폴더에 `skills/`가 생기지 않았다 |
| 대화 기록 | `projects/`가 생기지 않았다. `sessions/`는 빈 폴더 |
| 사람용 hook (ntfy 알림) | 이 폴더 설정을 쓰므로 돌지 않는다 |
| 비용 기록 필드 | `total_cost_usd`(이번 호출 $0.0079, 추정), `modelUsage`의 모델별 `inputTokens`·`outputTokens`·`cacheReadInputTokens`·`cacheCreationInputTokens`·`costUSD`·`costBasis` |

- **모델을 지정해야 한다.** 지정하지 않았더니 Pro 기본 모델(`claude-sonnet-5-5`)이 답했고, 보조 요청에 `claude-haiku-4-5`도 쓰였다. 그래서 실행 스크립트가 `--model`을 늘 넘긴다.
- **blogops를 붙인 뒤** (2026-10-07 5단계 시험 실행): Huninn은 blogops 툴만 불렀고, 허용되지 않은 도구를 쓰려 한 적(`permission_denials`)은 0회였다.

## Huninn 타이머 (sudo)

매장(`~/unattendant-live`)이 준비된 뒤 설치한다. 그 전에 켜면 `run-cycle.sh`가 없어 실패한다.

```bash
cd ~/unattendant-live
sudo install -m 644 ops/systemd/huninn-cycle.service ops/systemd/huninn-cycle.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start huninn-cycle.service    # 손으로 한 번 돌려 확인 (실제 사이클이다: 초안·승인 요청, 승인된 글이 있으면 발행)
journalctl -u huninn-cycle -n 30 --no-pager  # 결과 한 줄과 Huninn의 요약
sudo systemctl enable --now huninn-cycle.timer
systemctl list-timers huninn-cycle.timer     # 다음 실행 시각
```

| 설정 | 값 | 이유 |
| --- | --- | --- |
| 실행 | `Type=oneshot`, `User=hun` | 한 번 돌고 끝난다. 배포 키와 Huninn 설정 폴더가 이 계정에 있다 |
| 시각 | `OnCalendar=*-*-* 14:00:00 Asia/Seoul`, `Persistent=true` | [blogops.md](../docs/blogops.md) 10절 결정. Pi가 꺼져 있어 놓친 날은 켜진 뒤 한 번 돈다. 하루 1편 한도는 blogops가 지킨다 |
| 시간 제한 | `TimeoutStartSec=30min` | `cycle.py`가 25분에 먼저 멈추고 기록과 알림을 남긴다. 이건 마지막 안전장치 |
| `PATH` | `~/.local/bin` 포함 | claude, hugo, gitleaks가 여기 있다. systemd 기본 PATH에는 없다 |
| `DISABLE_AUTOUPDATER=1` | | claude 바이너리는 사람과 같이 쓴다. Huninn이 도는 동안에는 업데이트하지 않는다 |
| 쓰기 제한 | `ProtectSystem=strict` + `ReadWritePaths` | 매장, `~/.config/huninn`, `~/.cache`, `~/.local/state/claude`에만 쓸 수 있다. 작업실과 다른 프로젝트는 읽기만 된다. claude는 설정 폴더 밖에 MCP 로그(`~/.cache/claude-cli-nodejs/`, 툴 이름과 시간만)와 잠금 파일을 쓰고, hugo는 `~/.cache/hugo_cache`를 쓴다 |
| `MemoryMax=1G`, `Nice=10` | | 시험 실행에서 claude와 MCP 서버를 합친 RSS 최댓값이 312MB, 품질 검사 때 hugo 54MB·gitleaks 71MB가 더해진다. **지금은 메모리 cgroup이 꺼져 있어 `MemoryMax`가 걸리지 않는다** (아래 "메모리 제한") |

**시험 (2026-10-07)**: 매장이 아직 없어서, 경로만 작업실로 바꾼 같은 설정을 `systemd-run --user`로 돌렸다(`BLOGOPS_NO_PUBLISH=1`). 성공, 15.6초, 툴 3회, 추정 $0.015. 쓰기 제한 안에서 claude 로그인, MCP 서버, 디스코드 알림이 동작했다. 사용자 단위 서비스라 실제 시스템 유닛과 완전히 같지는 않고, 발행(git commit·push) 경로는 시험하지 않았다. 매장에서 손으로 처음 돌릴 때 확인한다.

## 초안 미리보기 호스트 (sudo)

승인 대기 초안을 폰에서 발행된 모습 그대로 읽는 주소 `https://preview.unattendant.dev/<토큰>/…`. 설계는 [blogops.md](../docs/blogops.md) 11절. 매장에서 Hugo로 구운 폴더(`state/previews/<토큰>/`)를 Caddy가 읽기 전용으로 내주고, 터널이 밖으로 연결한다. 토큰은 160비트 무작위 값이고 승인 대기가 끝나면 폴더가 지워진다.

| 구성 | 값 |
| --- | --- |
| Caddy | `:8081` 블록 (`ops/caddy/Caddyfile`). `127.0.0.1`에만 붙는다. 폴더 목록 없음, 점으로 시작하는 이름 차단, 읽기 전용 |
| 응답 헤더 | `X-Robots-Tag: noindex, nofollow, noarchive`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `/robots.txt` 전체 차단 |
| 공개 사이트에서 가져오는 것 | `/fonts/*`, `/status.json` 둘뿐. 사이트 CSS와 상태 띠가 절대 경로로 부른다. 글꼴(이름에 해시가 있는 공개 파일)만 캐시를 허용해 폰에서 페이지마다 다시 받지 않는다 |
| 터널 | `preview.unattendant.dev` → `127.0.0.1:8081` (`ops/cloudflared/config.yml`) |
| 주소 바꾸기 | 시험할 때 `BLOGOPS_PREVIEW_BASE_URL`로 기준 주소를 바꾼다 (기본 `https://preview.unattendant.dev`) |

켜는 순서 (PR이 main에 합쳐지고 매장이 `git pull`을 받은 뒤):

```bash
cd ~/unattendant-live
git pull --ff-only
# 1) 설정 검증 (서비스는 건드리지 않는다)
~/.local/bin/caddy validate --adapter caddyfile --config ops/caddy/Caddyfile
cloudflared --config ops/cloudflared/config.yml tunnel ingress validate
# 2) DNS: 기존 터널에 호스트 이름을 추가한다. Cloudflare에 CNAME이 하나 생긴다 (sudo 불필요)
cloudflared tunnel route dns unattendant preview.unattendant.dev
# 3) 반영 (sudo): Caddy와 터널을 다시 시작한다. 블로그가 1~2초 끊긴다
sudo systemctl restart unattendant-caddy unattendant-tunnel
systemctl is-active unattendant-caddy unattendant-tunnel
# 4) 확인: 8081이 열렸고, 토큰 없는 주소는 404
ss -ltn | grep ':8081 '
curl -s -o /dev/null -w '%{http_code}\n' https://preview.unattendant.dev/        # 404
curl -s -o /dev/null -w '%{http_code}\n' https://unattendant.dev/               # 200 (공개 사이트는 그대로)
```

승인 대기 초안이 있으면 `ops/huninn/review preview <초안ID>`로 미리보기를 만들고 주소를 본다. 폰에서 열리는지, 다크 모드와 그림이 보이는지 확인한다. 안 열리면 `systemctl status unattendant-tunnel`과 Caddy 로그를 본다.

**2026-10-13 시험 (임시 Caddy를 18081 포트에 띄워 실제 설정을 확인)**: 실제 사이트와 실제 승인 대기 초안으로 빌드 1초, 글 페이지·홈·CSS·글꼴 200. 토큰 없는 `/`, 엉뚱한 토큰, 점 폴더·파일, `..`·`%2e%2e` 경로 탈출은 모두 404, POST 405, PUT 404, 응답 헤더 위 표대로, 안내 띠는 초안 페이지에만 있다. 운영 중인 Caddy와 터널은 건드리지 않았다.

## Huninn 봇 (sudo)

디스코드 #승인 메시지의 [승인] [반려] [접기] 버튼을 받는 상시 프로세스 (`agent/blogops/bot.py`, 설계는 [blogops.md](../docs/blogops.md) 11절). 디스코드로 먼저 연결을 여는 방식이라 포트가 필요 없다. 봇 토큰, 운영자 ID, 채널 ID는 기존 `~/.config/huninn/huninn.env`에 이미 있다 (새 비밀값 없음).

```bash
cd ~/unattendant-live
git pull --ff-only
# discord.py 설치 (패키지 설치: discord.py, aiohttp 등 약 20MB, 선택 의존성 [bot])
cd agent && .venv/bin/pip install -e ".[bot]" && cd ..
# 접속만 확인한다 (메시지는 보내지 않는다. 봇이 2~3초 온라인으로 보인다)
BLOGOPS_ROOT=~/unattendant-live agent/.venv/bin/python -m blogops.bot --check
# 서비스 설치와 시작 (sudo)
sudo install -m 644 ops/systemd/huninn-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now huninn-bot
journalctl -u huninn-bot -n 20 --no-pager      # "접속했다: <봇 이름>" 줄 확인
systemctl show huninn-bot -p MemoryCurrent -p MemoryMax
```

| 설정 | 값 | 이유 |
| --- | --- | --- |
| 실행 | `Type=simple`, `User=hun`, `Restart=always` | 상주한다. 멈추면 버튼만 안 먹고 알림과 `review` 명령은 그대로라 10초 뒤 다시 띄우면 충분하다 |
| `BLOGOPS_ROOT` | 매장 | 매장의 `state/`를 다룬다 |
| `MemoryMax=200M` | | 상주 프로세스라 상한을 둔다. 메모리 cgroup은 2026-10-12에 켰다 |
| 쓰기 제한 | `ProtectSystem=strict` + `ReadWritePaths=매장/state 매장/logs` | 승인·반려 기록, 글감 상태(접기), 결정 로그, 미리보기 정리만 쓴다. 비밀값 파일은 읽기만 한다 |
| 권한 | 글을 쓰거나 발행하지 않는다. claude 토큰은 읽지 않는다 | 봇이 뚫려도 할 수 있는 일은 운영자 ID로 인증된 승인·반려뿐이다 |
| 디스코드 권한 | 인텐트 `guilds`만. 권한 인텐트는 쓰지 않는다 | 클릭(interaction)은 인텐트 없이 온다. 메시지 내용을 읽지 않는다 |

**순서 주의**: 매장이 새 코드를 받으면 다음 승인 요청부터 메시지에 버튼이 붙는다(사이클 시작 때 자동 `git pull`도 같다). 봇이 꺼져 있으면 그 버튼은 눌러도 "상호작용 실패"가 되니, 매장을 업데이트한 날 14:00 사이클 전에 봇부터 켜 둔다. 버튼이 안 될 때는 Pi에서 `review` 명령으로 승인한다(메시지에는 적지 않는다).

**시험 (2026-10-13)**
- `--check`로 실제 게이트웨이 접속 확인(권한 인텐트 없이).
- 가짜 interaction 단위 시험 14개: 운영자 아님·오래된 해시·확인 취소·접기·디스코드 오류 등.
- **실제 디스코드 시험 (20:36~20:37)**: 임시 폴더에 가짜 초안 3개를 만들어 실제 코드 경로(`notify.request_approval`)로 #승인에 보내고(디스코드가 버튼·링크 payload를 그대로 받았다, 미리보기 3개 빌드), 임시 봇을 띄워 두고 운영자가 폰에서 눌렀다. 승인(확인 창 → [승인 확정]), 반려(사유 입력창), 접기(사유 입력창) 모두 기록이 `via: discord`로 남았고, 원본 메시지가 결과로 바뀌며 버튼이 사라졌고(`close_approval_message` 3건), 미리보기 폴더가 지워졌다. 접기는 초안 `held` + 글감 `blocked`, 반려만으로는 글감이 그대로였다. 봇 로그에 경고·오류 없음, 거부(`approval_denied`) 0건. 승인 확인 창의 [취소]는 로그가 남지 않아 확인하지 못했다(단위 시험만).
- 시험 중 발견해 고친 것: `bot.run(root_logger=True)`가 없으면 `blogops.*` 로거의 INFO("접속했다" 등)가 journal에 나오지 않는다.
- 아직 못 한 것: [미리보기] 링크가 폰에서 열리는지(DNS·Caddy 반영 전이라 열리지 않는 게 정상), 매장에서 상주 서비스로 도는 것.

## 반려·접기 직후 바로 쓰기 (sudo)

운영자가 반려하거나 접으면 14:00을 기다리지 않고 사이클을 바로 한 번 더 돌린다 (하루 5회까지, 승인은 해당 없음). 설계는 [blogops.md](../docs/blogops.md) 12절. 봇이나 `review` 명령이 `logs/.cycle-request` 파일을 쓰면 path 유닛이 `huninn-cycle.service`를 시작하고, 서비스가 시작하며 그 파일을 지운다.

```bash
cd ~/unattendant-live
git pull --ff-only
# 바뀐 서비스(ExecStartPre 한 줄 추가)와 새 path 유닛을 설치한다 (sudo). 타이머는 그대로다
sudo install -m 644 ops/systemd/huninn-cycle.service ops/systemd/huninn-cycle-now.path /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now huninn-cycle-now.path
# 확인: active, 지켜보는 파일이 매장의 요청 파일
systemctl show huninn-cycle-now.path -p ActiveState -p Paths
systemctl list-timers huninn-cycle.timer            # 타이머는 그대로 다음 14:00
```

| 설정 | 값 | 이유 |
| --- | --- | --- |
| `PathExists` | `~/unattendant-live/logs/.cycle-request` | `logs/`는 git 제외다. `state/`에 두면 사이클 끝의 state 커밋에 딸려 올라간다 |
| `ExecStartPre` (서비스) | `rm -f` 요청 파일 | 요청 하나에 한 번만 돈다. 도는 중에 새 요청이 오면 끝난 뒤 한 번 더 돈다. 타이머가 먼저 돌아도 그 실행이 요청을 처리한다. `cycle.py`도 시작할 때 같은 파일을 지운다(두 유닛 파일을 같이 설치할 것) |
| `TriggerLimit` | 1시간에 8번 | 요청 파일이 지워지지 않는 고장이 나도 계속 돌지 않게 한다. 정상이면 하루 5번이 한도다(blogops가 센다) |
| 하루 5회 상한 | `Config.ondemand_daily_limit` (KST) | 받아들인 요청을 `logs/YYYY-MM-DD.jsonl`의 `cycle_requested`로 센다. 넘으면 요청하지 않고 다음 14:00 사이클로 안내한다 |
| 권한 | 봇과 `review`는 파일만 쓴다 | 서비스 시작 권한(polkit)을 주지 않는다 |

**순서**: 코드를 먼저 배포하고 이 유닛을 나중에 켜도 된다. `systemctl show huninn-cycle-now.path`로 유닛이 켜져 있고 이 설정의 요청 파일을 지켜볼 때만 "사이클을 바로 돌린다"고 말하고, 아니면 "다음 14:00 사이클에서"라고 안내한다.

**첫 확인**: 승인 대기 초안을 하나 반려해(사유 입력) 1~2분 안에 #승인에 새 승인 요청이 오는지 본다. `journalctl -u huninn-cycle -n 20 --no-pager`, `logs/cycles.jsonl`에 사이클이 하나 더 생기고 `logs/<날짜>.jsonl`에 `cycle_requested`(granted)가 남는다. 접기는 새 글감으로 새 초안이 온다. 실제 사이클이 돌아 구독 한도를 쓰니 시험 삼아 누르지는 말 것.

**끄기**: `sudo systemctl disable --now huninn-cycle-now.path`. 이후 반려·접기는 다음 14:00 사이클에서 처리된다고 안내한다(코드 변경 없음).

**2026-10-13 시험 (사용자 매니저의 임시 유닛, 같은 systemd 257)**: 요청 파일 1번 → 서비스 1번 실행 후 파일 삭제, 실행 중 요청 → 끝나자마자 1번 더, 실행 전 3번 연속 요청 → 1번만. 실제 `ondemand.request`로도 확인했다: 같은 경로를 지켜보면 `watcher_active` True, 다른 경로면 False, 파일 쓰기(임시 파일 → 이름 바꾸기)에도 유닛이 반응해 1.5초 안에 서비스가 시작됐고, 실행 중 두 번째 요청은 끝난 뒤 한 번 더 돌았다. 시험 유닛은 지웠다. 시스템 유닛 설치는 아직 하지 않았다.

## 메모리 제한 (cgroup)

2026-10-07 확인: **이 Pi는 메모리 cgroup이 꺼져 있다.** 부트로더가 커널 명령줄에 `cgroup_disable=memory`를 붙이고(`/boot/firmware/cmdline.txt`에는 없다), 부팅 로그에 `cgroup: Disabling memory control group subsystem`이 남는다. `/sys/fs/cgroup/cgroup.controllers`에도 `memory`가 없다.

그래서 유닛의 `MemoryMax`는 지금 효과가 없다. `unattendant-caddy`의 `MemoryMax=200M`도 걸려 있지 않다(`systemctl show`에 값은 있지만 `MemoryCurrent=[not set]`). CLAUDE.md의 "실험은 systemd 서비스 + MemoryMax로만 돌린다"도 이 상태로는 지켜지지 않는다.

켜는 방법 (아직 하지 않았다. 운영자가 정한다):

```bash
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak
sudo sed -i '1 s/$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt   # 한 줄짜리 파일의 끝에 붙인다
cat /boot/firmware/cmdline.txt                                                          # 한 줄인지 확인
sudo reboot
grep memory /sys/fs/cgroup/cgroup.controllers                                          # 재부팅 뒤 확인
```

- `cmdline.txt`는 한 줄이어야 한다. 줄이 나뉘면 부팅하지 못할 수 있다. Tailscale로만 접속하는 중이면 백업과 확인을 먼저 한다.
- 켜면 커널이 메모리 사용을 추적하느라 메모리를 조금 더 쓴다. Raspberry Pi가 기본으로 꺼 둔 이유다.

## 버전 기록

| 도구 | 버전 | 설치일 |
| --- | --- | --- |
| Hugo extended | 0.167.0 | 2026-10-06 |
| Caddy | 2.11.7 | 2026-10-06 |
| gitleaks | 8.30.1 | 2026-10-06 |
| cloudflared | 2026.9.1 (deb, `/usr/bin`) | 기존 |
