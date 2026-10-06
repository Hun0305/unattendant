# pre-commit 비밀키 스캐너

두 레포(`~/unattendant`, `~/unattendant/site`)는 커밋 직전에 비밀값 검사를 거치고, 걸리면 커밋이 만들어지지 않는다. Huninn이 사람 없이 커밋하는 구조라서, 공개 레포에 키가 올라가는 사고를 사람이 보기 전에 막는 장치다. 2026-10-06에 붙였다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `ops/install-gitleaks.sh` | gitleaks 8.30.1 arm64 바이너리를 체크섬 검증 후 `~/.local/bin`에 설치하고, 두 레포의 `core.hooksPath`를 `ops/githooks`로 연결한다 |
| `ops/githooks/pre-commit` | 커밋 직전에 실행되는 훅. 두 레포가 같은 파일을 쓴다 |
| `ops/gitleaks.toml` | gitleaks 규칙 (아래 "규칙") |
| `ops/test-pre-commit.sh` | 임시 레포에서 가짜 비밀값으로 커밋을 시도해 훅이 막는지 확인한다 |

훅은 `.git/hooks`가 아니라 레포 안의 `ops/githooks`에 두었다. `.git/hooks`는 git이 추적하지 않아서, Pi를 새로 세우면 사라지기 때문이다. 새 Pi에서는 `ops/install-gitleaks.sh`를 한 번 실행하면 된다.

## 검사 순서

1. **금지 파일 이름**: 스테이징된 파일 중 `.env`, `.env.*`, `*.pem`, `*.key`, `logs/` 아래 파일, `state/drafts/`·`state/approvals/` 아래 파일, SSH 키 파일(`id_rsa` 등)이 있으면 막는다. `.gitignore`를 `git add -f`로 우회한 경우에 대비한 것이다.
2. **비밀값 패턴**: `gitleaks git --pre-commit --staged --redact`로 스테이징된 변경 내용을 검사한다. 걸린 값은 가려서 출력한다.

오탐이면 그 줄 끝에 `gitleaks:allow` 주석을 단다. `git commit --no-verify`로 훅을 건너뛰지 않는다(CLAUDE.md 커밋 규칙).

## 규칙

gitleaks 기본 규칙 222개 중 이 프로젝트와 관련 있는 18개를 v8.30.1의 `config/gitleaks.toml`에서 그대로 옮기고, 전용 규칙 6개를 더했다. 기본 규칙을 전부 쓰지 않는 이유는 아래 "실험 기록 1"에 있다.

| 출처 | 규칙 |
| --- | --- |
| 기본 (18) | `anthropic-api-key`, `anthropic-admin-api-key`, `openai-api-key`, `cloudflare-api-key`, `cloudflare-global-api-key`, `cloudflare-origin-ca-key`, `discord-api-token`, `discord-client-id`, `discord-client-secret`, `github-pat`, `github-fine-grained-pat`, `github-oauth`, `github-app-token`, `github-refresh-token`, `gcp-api-key`, `private-key`, `jwt`, `generic-api-key` |
| 전용 (6) | `cloudflared-tunnel-secret`: 터널 자격증명 json의 TunnelSecret 값 |
| | `cloudflared-cert`: `~/.cloudflared/cert.pem`의 ARGO TUNNEL TOKEN 헤더 |
| | `cloudflared-tunnel-token`: 대시보드 관리형 터널의 실행 토큰 |
| | `discord-bot-token`: 디스코드 봇 토큰 (기본 `discord-api-token`은 봇 토큰 형식을 잡지 못한다) |
| | `discord-webhook-url`: 디스코드 웹훅 URL (업타임 모니터 알림용) |
| | `anthropic-credential`: `sk-ant-<종류>-…` 형식의 Anthropic 자격증명 전반. Claude Code 구독 토큰(`claude setup-token`)을 잡으려고 추가했다. 기본 규칙 두 개는 API 키(`sk-ant-api03-`)와 Admin 키(`sk-ant-admin01-`) 형식만 잡는다. 종류와 길이를 몰라도 걸리게 넓게 잡고, 자리표시자(`xxxx…`)는 entropy 3.5 미만이라 걸러진다 |

새 서비스의 키를 쓰게 되면(예: Google Search Console 서비스 계정, UptimeRobot API 키) gitleaks 기본 config에서 그 서비스 규칙을 찾아 `ops/gitleaks.toml`에 추가하고, `ops/test-pre-commit.sh`에 경우를 하나 더한다.

## 실험 기록 (2026-10-06)

테스트 중 만든 임시 레포와 출력 파일은 지웠기 때문에, 원본 로그는 남아 있지 않다. 아래 수치는 그때 터미널에 찍힌 값을 옮긴 것이고, 4는 `ops/test-pre-commit.sh`로 다시 측정한 결과다.

### 1. 기본 규칙 전체는 Pi 4에서 너무 느리다

같은 내용(64바이트 json 한 줄)을 스테이징하고 gitleaks 한 번의 실행 시간을 쟀다.

| 설정 | 규칙 수 | 시간 |
| --- | --- | --- |
| 기본 규칙 전체 (`useDefault = true`) + 전용 규칙 | 225 | 34.9초 |
| 전용 규칙만 (`useDefault = false`) | 3 | 0.6초 |
| 참고: `gitleaks version` | — | 0.4초 |

검사할 내용은 64바이트뿐인데 34초가 걸렸으므로, 시간은 내용이 아니라 규칙 수(시작할 때 정규식을 준비하는 비용)에서 나온다. 커밋할 때마다 35초를 기다릴 수는 없어서 규칙을 골라 쓰기로 했다.

### 2. 고른 규칙(18 + 6)은 커밋당 4\~6초

같은 방식으로 재면 커밋 한 번(훅 포함)에 4\~6초가 걸린다. 전용 규칙만 쓸 때(0.6초)보다 느린 건 기본 규칙 중 일부가 무겁기 때문으로 보인다. `generic-api-key`가 가장 유력하지만 규칙별로 재보지는 않았다. 지금 속도로 충분해서 더 줄이지 않았다.

### 3. 기존 히스토리와 작업 트리

| 대상 | 결과 |
| --- | --- |
| 운영 레포 히스토리 (3커밋, 당시 Private) | 검출 0건 |
| site 레포 히스토리 (1커밋) | 검출 0건 |
| 커밋 전 작업 트리 전체 (약 106KB) | 검출 0건, 5.2초 |

`anthropic-credential` 규칙을 추가한 뒤 다시 검사했다(같은 날 17:49).

| 대상 | 결과 |
| --- | --- |
| 운영 레포 히스토리 (16커밋) | 검출 0건 |
| site 레포 히스토리 (5커밋) | 검출 0건 |
| 작업 트리 전체 (약 309KB, git 제외 파일 포함) | 4건, 모두 `.env`(디스코드 봇 토큰·웹훅 URL·클라이언트 ID). `.env`는 git이 추적하지 않고 훅 1단계에서도 막힌다. 실제 디스코드 토큰을 기존 규칙이 잡는다는 확인이기도 하다. 값은 출력하지 않고 규칙 이름과 위치만 봤다 |

### 4. 동작 테스트

`ops/test-pre-commit.sh` 결과. 가짜 값은 실행할 때 무작위로 만든다.

| 경우 | 기대 | 결과 | 시간 |
| --- | --- | --- | --- |
| 평범한 문서 (터널 UUID 포함) | 통과 | 통과 | 4.3초 |
| 문서 속 키 형식 설명 (`sk-ant-api03-…`, `xxxx` 자리표시자) | 통과 | 통과 | 4.3초 |
| Anthropic API 키 | 차단 | 차단 | 5.9초 |
| Claude Code 구독 토큰 (`CLAUDE_CODE_OAUTH_TOKEN=` 대입) | 차단 | 차단 | 6.0초 |
| Claude Code 구독 토큰 (로그 문장에 섞임) | 차단 | 차단 | 4.2초 |
| 디스코드 봇 토큰 | 차단 | 차단 | 5.7초 |
| 디스코드 웹훅 URL | 차단 | 차단 | 4.8초 |
| GitHub PAT | 차단 | 차단 | 4.2초 |
| 터널 자격증명 json | 차단 | 차단 | 5.3초 |
| cloudflared cert.pem | 차단 | 차단 | 4.2초 |
| SSH 개인 키 | 차단 | 차단 | 4.9초 |
| `.env` 파일 | 차단 | 차단 | 0.0초 |
| `logs/` 아래 파일 | 차단 | 차단 | 0.0초 |
| 미발행 초안 `state/drafts/` | 차단 | 차단 | 0.0초 |
| 승인 상태 `state/approvals/` | 차단 | 차단 | 0.0초 |

15개 경우 모두 기대대로 나왔다. 초안·승인 상태 2개는 공개 범위 결정 후, 구독 토큰 2개와 문서 형식 1개는 `anthropic-credential` 추가 때 넣었다. 나머지 경우의 시간은 첫 측정 값이다. 터널 UUID는 자격증명 파일 없이는 쓸 수 없는 값이라 통과하는 게 맞다. `.env`, `logs/`, 초안·승인 상태는 1단계(파일 이름)에서 막혀서 gitleaks까지 가지 않는다.

### 5. 구독 토큰은 기본 규칙으로 막히지 않았다

`anthropic-credential` 규칙을 넣기 전에 테스트 경우만 먼저 추가해 돌렸다.

| 경우 | 규칙 추가 전 | 규칙 추가 후 |
| --- | --- | --- |
| 구독 토큰을 `CLAUDE_CODE_OAUTH_TOKEN=`에 대입 | **커밋됨** | 차단 |
| 구독 토큰이 로그 문장에 섞임 | **커밋됨** | 차단 |
| 문서 속 키 형식 설명 | 통과 | 통과 |

변수 이름에 `TOKEN`이 들어가도 기본 `generic-api-key` 규칙이 잡지 못했다. 2026-10-07에 발급한 실제 토큰으로 확인했다. `.env`를 값은 가리고 규칙 이름과 위치만 출력하게 검사했다. 토큰은 `sk-ant-oat01-…` 형식, 108자 한 줄이었고 **`anthropic-credential`에만 걸렸다**(entropy 5.56). 기본 규칙(`anthropic-api-key`, `generic-api-key`)은 하나도 걸리지 않아서, 이 규칙이 없었다면 실제 토큰도 그대로 커밋됐을 것이다.

## 다시 확인하는 법

```bash
ops/test-pre-commit.sh                         # 동작 테스트 (결과 표 출력)
gitleaks git --redact --config ops/gitleaks.toml .      # 운영 레포 히스토리 전체
gitleaks git --redact --config ops/gitleaks.toml site   # site 레포 히스토리 전체
```

규칙을 바꾸거나 gitleaks 버전을 올린 뒤에는 `ops/test-pre-commit.sh`를 다시 돌려 위 표와 비교한다.

## 한계

- `--no-verify`로 건너뛸 수 있다. 강제 장치가 아니라 실수를 막는 안전망이다.
- 패턴으로 찾기 때문에 형식이 특이한 비밀값은 놓칠 수 있다.
- 두 번째 방어선으로 GitHub Secret Scanning + Push Protection을 쓴다(공개 레포 무료, 레포 Settings → Code security). 2026-10-06에 두 레포 모두 켰다. GitHub도 알려진 형식만 잡으므로 cloudflared 자격증명 같은 전용 형식은 이 훅이 1차 방어선이다.
