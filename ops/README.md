# ops

Pi에서 블로그를 띄우는 데 필요한 설정과 설치 기록. 다른 프로젝트(TrueETA 등)의 서비스·포트는 건드리지 않는다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `install-site-tools.sh` | Hugo extended, Caddy를 GitHub 릴리스 arm64 바이너리로 `~/.local/bin`에 설치 (체크섬 검증, sudo 불필요) |
| `caddy/Caddyfile` | `site/public`을 `127.0.0.1:8080`에 서빙. TLS는 Cloudflare가 맡는다 |
| `systemd/unattendant-caddy.service` | Caddy 상시 실행 |
| `cloudflared/config.yml` | Named Tunnel `unattendant` ingress (`unattendant.dev` → `127.0.0.1:8080`) |
| `systemd/unattendant-tunnel.service` | 터널 상시 실행 |
| `install-log2ram.sh` | log2ram 설치 (Debian 패키지, 기본 설정, sudo, 재부팅 필요) |
| `install-gitleaks.sh` | gitleaks 설치 + 두 레포의 `core.hooksPath`를 `ops/githooks`로 연결 |
| `githooks/pre-commit` | 커밋 직전 검사: 금지 파일(`.env`, `*.pem`, `*.key`, `logs/`, `state/drafts/`, `state/approvals/`, SSH 키) + gitleaks 비밀값 패턴 |
| `test-pre-commit.sh` | 임시 레포에서 가짜 비밀값으로 훅 동작 확인 |
| `gitleaks.toml` | gitleaks 규칙. 기본 규칙 중 18개 + 전용 규칙 6개(cloudflared 자격증명·인증서·토큰, 디스코드 봇 토큰·웹훅, Claude Code 구독 토큰을 포함한 Anthropic 자격증명 전반) |

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

두 레포 모두 공개다. 비공개는 비밀값(`.env`, `~/.cloudflared/`, `~/.ssh/`), 원본 로그(`logs/`), 미발행 초안(`state/drafts/`, `state/approvals/`)뿐이고 `.gitignore`와 pre-commit 훅이 막는다. 자세한 기준은 [architecture.md](../docs/architecture.md)의 저장소 섹션에 있다.

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
install -d -m 700 ~/.config/huninn ~/.config/huninn/claude   # 2026-10-06 생성
# Phase 1 실행 형태 (예정)
CLAUDE_CONFIG_DIR=~/.config/huninn/claude CLAUDE_CODE_OAUTH_TOKEN=... claude -p "..." --output-format json
```

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

**Phase 1에서 정할 것** (`settings.json`, blogops와 함께)

- 허용 툴: blogops MCP 툴만 허용하고 Bash·파일 쓰기 같은 범용 툴은 끈다 (architecture.md: AI는 정해진 툴로만 시스템을 건드린다).
- 위의 `claudeMdExcludes`.
- auto memory: Huninn의 상태는 `state/`에만 두도록 `autoMemoryEnabled: false`를 검토한다.
- 대화 기록 보존: 기본 30일(`cleanupPeriodDays`). SD카드 쓰기를 줄이려면 `--no-session-persistence`로 끄고, 필요한 것만 `logs/` JSONL에 남긴다.
- 구독 토큰으로 돌렸을 때 claude.ai 동기화 스킬이 이 폴더에 생기는지 토큰 발급 후 확인한다.

## 버전 기록

| 도구 | 버전 | 설치일 |
| --- | --- | --- |
| Hugo extended | 0.167.0 | 2026-10-06 |
| Caddy | 2.11.7 | 2026-10-06 |
| gitleaks | 8.30.1 | 2026-10-06 |
| cloudflared | 2026.9.1 (deb, `/usr/bin`) | 기존 |
