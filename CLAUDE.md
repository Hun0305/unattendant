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
- ops/         systemd 유닛, cloudflared 설정, 설치 스크립트
- 비밀값은 .env에만 둔다. .env, logs/, site/는 비공개 레포 .gitignore에 포함
- docs/        설계·계획 문서 (아래 참고)

## 문서 (docs/)
- docs/architecture.md: 설계 문서 사본. 구조나 설계 판단이 필요하면 먼저 읽을 것
- docs/hardware-plan.md: 장비 역할 분담, WOL 원격 작업
- docs/edge-ai-blog-topics.md: 실험 주제(비전·LLM 시리즈)와 측정 원칙
- docs/reference.md: 참고 자료
- docs/todo.md: 현재 할 일. 작업을 끝내면 여기에 체크할 것
- docs/와 실제 상태가 다르면 임의로 고치지 말고 먼저 물어볼 것

## 규칙
- sudo가 필요한 명령, 서비스 재시작, 패키지 설치는 실행 전에 무엇을 왜 하는지 먼저 말할 것
- 시스템 설정 변경은 ops/에 스크립트나 메모로 남겨서 재현할 수 있게 할 것
- 비밀값(API 키, 토큰)을 출력하거나 커밋하지 말 것
- SD카드 쓰기를 줄일 것: 큰 임시 파일은 /tmp(RAM)에 두고, 로그는 회전시킬 것
- 실험은 systemd 서비스 + MemoryMax로만 돌리고, VS Code 원격 연결 중에는 LLM 실험을 돌리지 말 것
- 답변은 한국어로 간결하게

태그라인
- EN: unattendant — the attendant who isn't there. A blog run by Huninn, an AI living on a Raspberry Pi.
- KO: unattendant — 자리에 없는 당번. 라즈베리파이 위에서 AI 'Huninn'이 혼자 운영하는 블로그.