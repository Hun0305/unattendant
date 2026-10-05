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
| `gitleaks.toml` | gitleaks 규칙. 기본 규칙 중 18개 + 전용 규칙 5개(cloudflared 자격증명·인증서·토큰, 디스코드 봇 토큰·웹훅) |

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
- 확인(2026-10-06): 가짜 Anthropic 키, 디스코드 봇 토큰·웹훅, GitHub PAT, 터널 자격증명 json, cert.pem, SSH 개인 키, `.env` 모두 차단, 평범한 문서는 통과. 기존 히스토리(운영 레포 3커밋, site 1커밋)는 검출 0건.

## 버전 기록

| 도구 | 버전 | 설치일 |
| --- | --- | --- |
| Hugo extended | 0.167.0 | 2026-10-06 |
| Caddy | 2.11.7 | 2026-10-06 |
| gitleaks | 8.30.1 | 2026-10-06 |
| cloudflared | 2026.9.1 (deb, `/usr/bin`) | 기존 |
