# unattendant.dev

라즈베리파이 위에서 AI 에이전트 Huninn이 혼자 운영하는 블로그.
설계 문서(기준 문서): /docs/architecture.md

## 환경
- Raspberry Pi 4B 4GB, Raspberry Pi OS 64비트 (Debian 13 trixie), 콘솔 부팅
- 같은 Pi에 다른 프로젝트가 있음 (~/Pi_Server, ~/TrueETA 등). 절대 수정·중지·삭제하지 말 것
- 포트: 블로그 Caddy 8080.
- cloudflared는 이미 설치돼 있음. 기존 터널에 호스트 이름을 추가하는 방식으로 쓸 것
- Tailscale은 원격 접속 경로라 설정을 바꾸지 말 것

## 구조
- site/        Hugo 사이트 (ko는 /, en은 /en/). 별도 공개 레포
- agent/       Huninn 루프, blogops, MCP 서버, 디스코드 봇, 대시보드
- experiments/ 실험 템플릿과 결과 CSV
- state/       strategy.md, 백로그, 초안, 승인 상태
- logs/        JSONL 로그 (git 제외)
- ops/         systemd 유닛, cloudflared 설정, 설치 스크립트, pre-commit 훅
- 레포 두 개(사이트 레포 Hun0305/unattendant.dev, 운영 레포 Hun0305/unattendant) 모두 공개다
- 비공개는 비밀값(.env, ~/.cloudflared, ~/.ssh), 원본 로그(logs/), 미발행 초안(state/drafts/, state/approvals/)뿐이다. 모두 운영 레포 .gitignore로 빼고(site/도 포함), Pi와 백업에만 둔다
- docs/        설계·계획 문서 (아래 참고)

## 문서 (docs/)
- docs/architecture.md: 설계 기준 문서. 무엇을 왜 만드는지(설계, 스택, 툴 스펙, 가드레일). 진행 상황은 넣지 않는다. 구조나 설계 판단이 필요하면 먼저 읽을 것
- docs/hardware-plan.md: 장비 역할 분담, WOL 원격 작업
- docs/edge-ai-blog-topics.md: 실험 주제(비전·LLM 시리즈)와 측정 원칙
- docs/reference.md: 참고 자료
- docs/layout-options.md: 블로그 레이아웃 5안과 AI 운영 사이트 19곳 화면 조사 (2026-10-06)
- docs/pre-commit.md: 비밀키 스캐너(gitleaks pre-commit 훅) 구성, 규칙, 실험 기록
- docs/todo.md: 로드맵(단계·게이트), 단계별 체크리스트, 열린 질문. 언제 무엇을 어디까지 했는지. 작업을 끝내면 여기에 체크할 것
- docs/와 실제 상태가 다르면 임의로 고치지 말고 먼저 물어볼 것
- 로컬 docs/가 유일한 기준이다. 온라인 설계 문서(claude.ai artifact)는 2026-10-06부터 갱신하지 않으므로 읽거나 동기화하지 말 것

## 규칙
- sudo가 필요한 명령, 서비스 재시작, 패키지 설치는 실행 전에 무엇을 왜 하는지 먼저 말할 것
- 시스템 설정 변경은 ops/에 스크립트나 메모로 남겨서 재현할 수 있게 할 것
- 비밀값(API 키, 토큰)을 출력하거나 커밋하지 말 것
- .env에 새 비밀값을 추가하면 ops/gitleaks.toml에 그 서비스 규칙이 있는지 확인하고, 없으면 추가한 뒤 ops/test-pre-commit.sh에 경우를 더할 것 (자세한 건 docs/pre-commit.md)
- SD카드 쓰기를 줄일 것: 큰 임시 파일은 /tmp(RAM)에 두고, 로그는 회전시킬 것
- 실험은 systemd 서비스 + MemoryMax로만 돌리고, VS Code 원격 연결 중에는 LLM 실험을 돌리지 말 것
- 답변은 한국어로 간결하게

## 커밋 규칙
Conventional Commits 형식을 쓴다: `type(scope): 요약`

type
- feat: 새 기능 (예: 디스코드 봇 승인 버튼)
- fix: 버그 수정
- docs: 문서 (docs/, README, CLAUDE.md)
- chore: 설정·의존성·잡일 (패키지 설치, .gitignore)
- refactor: 동작은 같고 구조만 바꿈
- ops: 서버·배포 설정 (systemd, Caddy, cloudflared)
- content: Huninn이 발행한 글 (사람이 직접 쓰지 않음)
- exp: 실험 템플릿과 결과 데이터

scope: site, agent, mcp, bot, dashboard, exp 중 하나 (애매하면 생략)
- ops는 scope가 아니라 type이다. 서버·배포 설정은 `chore(ops):`가 아니라 `ops:`로 쓴다

작성 규칙
- 요약은 50자 안쪽, 마침표 없이, 무엇을 했는지 쓴다
- 본문은 반드시 쓴다. 한 줄 띄우고 아래를 적는다
  - 무엇을 바꿨는지 (파일·기능 단위로)
  - 왜 바꿨는지 (배경, 문제)
  - 어떻게 확인했는지 (실행한 명령, 결과)
- 하나의 커밋에는 하나의 논리적 변경만 담는다. 성격이 다르면 나눠서 커밋한다
- 커밋 전에 git diff로 .env, 토큰, logs/가 포함되지 않았는지 확인한다
- pre-commit 훅(gitleaks)을 `--no-verify`로 건너뛰지 않는다. 오탐이면 그 줄에 `gitleaks:allow`를 단다
- 커밋과 push는 내가 요청했을 때만 한다

예시
    ops(site): Caddy로 Hugo 정적 사이트를 8080에 서빙

    - ops/Caddyfile 추가: site/public을 :8080에서 서빙
    - ops/systemd/caddy-site.service 추가, 부팅 시 자동 시작

    왜: 기존 프로젝트 포트(8099)와 겹치지 않게 블로그 전용 포트를 분리
    확인: curl -I localhost:8080 → 200 OK, 재부팅 후에도 자동 기동

## 브랜치 규칙
- main은 Pi에서 실제로 돌아가는 버전이다. 항상 동작하는 상태를 유지한다
- 문서·설정·작은 수정은 main에 바로 커밋해도 된다
- 에이전트, MCP, 봇처럼 동작을 바꾸는 큰 작업은 feat/, fix/ 브랜치에서 하고 PR로 합친다
- 브랜치 이름: feat/짧은-설명, fix/짧은-설명 (예: feat/discord-approval)
- PR은 squash merge, 합친 브랜치는 삭제한다

태그라인
- EN: unattendant — the attendant who isn't there. A blog run by Huninn, an AI living on a Raspberry Pi.
- KO: unattendant — 자리에 없는 당번. 라즈베리파이 위에서 AI 'Huninn'이 혼자 운영하는 블로그.