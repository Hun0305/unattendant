# unattendant.dev — 로드맵과 진행 상황

이 문서는 **언제, 무엇을, 어디까지 했는지**를 다룬다. 로드맵, 단계별 체크리스트, 열린 질문이 여기 있다.
**무엇을 왜 그렇게 만드는지**(설계, 스택, 툴 스펙, 가드레일)는 [architecture.md](architecture.md)에 있다.

기준은 로컬 `docs/`다. 이전에 쓰던 온라인 설계 문서(https://claude.ai/code/artifact/c5cf2218-acfe-4130-996d-4204c9854189)는 2026-10-06부터 갱신하지 않는다.

## 로드맵

네 단계로 나누고, 각 단계는 게이트를 통과해야 다음으로 넘어간다. 기간은 예상치다. 핵심은 승인 모드를 해제하는 게이트 3이다.

| 단계 | 기간 | 내용 | 다음 단계로 가는 게이트 |
| --- | --- | --- | --- |
| Phase 0 · 기반 준비 | 약 1주 | 도메인 구매(B1), Cloudflare Named Tunnel, Hugo 사이트와 테마, Caddy 서빙. 검색엔진 3곳 등록, AI 크롤러 허용, GitHub 레포 2개 | 1: 도메인으로 사이트가 열리고 첫 글(사람이 직접 쓴 소개글)이 색인된다 |
| Phase 1 · 반자동 루프 (C3) | 1\~2주 | blogops 핵심 툴(`create_draft`, `check_quality`, `publish_post`, `request_indexing`). Claude Code headless로 일간 루프 검증, 모든 글은 사람이 승인. Pro 구독으로 돌리고 크레딧은 결제하지 않는다 | 2: AI가 쓴 글 5개 발행, 품질 게이트 통과율 기록 시작 |
| Phase 2 · 자율 루프 (C2) | 2\~4주 | API 크레딧 결제 시작. 자체 루프와 예산 상한, 실험 러너(비전·LLM)와 공통 로거, JSONL 로깅, 운영 대시보드, 디스코드 알림. 주간 보고서 자동 발행, 전략 문서 자동 갱신 | 3: 2주 연속 사람 개입 0회, 품질 첫 통과율 80% 이상 → 승인 모드 해제 |
| Phase 3 · 완전 자율과 확장 | 이후 상시 | 자동 발행, 공개 운영 현황 페이지, blog-mcp를 다른 사람도 쓸 수 있게 패키지로 정리(코드는 처음부터 공개), 커뮤니티 배포. WOL로 작업 장비 연동(양자화·오프로딩), 필요하면 SSD 이전·Cloudflare Pages 대기 미러 | — |

## 현재 단계: Phase 0 (기반 준비)

- [x] 이름 확정: unattendant.dev, 에이전트 Huninn (탈락 후보 nobodywrites, daysunattended, lefttorun, pilog, unattended.\*, araseo, untended.garden 등과 이름 짓는 과정은 첫 글감)
- [x] Cloudflare에서 unattendant.dev 구매 (자동 갱신, 계정 2단계 인증. 만료 2027-10-06)
- [x] 기존 Pi 정리 (2026-10-06 확인)
  - [x] 콘솔 부팅 (`multi-user.target`)
  - [x] Samba 끄기 (smbd·nmbd disabled)
  - [x] PackageKit (inactive. static 유닛이라 요청이 있을 때만 뜬다)
  - ~~Bluetooth 자동 시작 끄기~~ 하지 않기로 함 (2026-10-06). 지금은 inactive, enabled 상태 그대로
  - ~~unattended-upgrades 설치~~ 하지 않기로 함 (2026-10-06). 보안 업데이트는 사람이 `apt upgrade`로 직접
  - [x] zram 스왑 (`/dev/zram0` 2GB)
  - [x] log2ram 설치 (1.7.2, ops/install-log2ram.sh, 2026-10-06). 재부팅 후 `/var/log`가 log2ram tmpfs(128M 상한, 2.8M 사용)로 마운트됨, log2ram-daily.timer 동작
  - [x] 방열판·팬 케이스
- [x] Hugo(extended, arm64), Caddy 설치 (Hugo 0.167.0, Caddy 2.11.7 → ~/.local/bin, ops/install-site-tools.sh)
- [x] site/에 다국어 Hugo 뼈대 + "곧 시작" 페이지 (태그라인 포함)
- [x] 글 템플릿 (2026-10-06): 단일 글·목록·태그 페이지, 작성 주체 표시(기본 Huninn, `author: human`이면 사람), 광고 표시, 영어판 안내, 출처 목록, RSS·OpenGraph. 화면은 docs/layout-options.md E안(Pi 상태 띠, 글·시리즈·숫자·소개 메뉴, 1단 목록, 시리즈 4개, 소개·숫자 페이지). 글 형식은 site/README.md
- [x] Caddy로 site/public을 8080에 서빙 (unattendant-caddy.service, 127.0.0.1:8080)
- [x] ~~기존 cloudflared 터널에~~ unattendant.dev → localhost:8080 추가
  - 2026-10-06 확인: 기존은 TrueETA Quick Tunnel뿐이고 Named Tunnel이 없어서 새로 만듦
  - [x] Named Tunnel `unattendant` 생성 (id bd749433-…), DNS CNAME 연결, 임시 실행으로 https 200 확인
  - [x] unattendant-tunnel.service 등록
- [x] 외부(LTE)에서 https://unattendant.dev 접속 확인 (2026-10-06)
- [x] Cloudflare AI 크롤러 허용: Search·Agent·Training 모두 Allow, Bot Preference Sync 끔, AI Labyrinth·Bot fight mode 끔 (2026-10-06)
- [x] GitHub 레포 2개 연결 (2026-10-06): 사이트 레포 Hun0305/unattendant.dev ← site/, 운영 레포 Hun0305/unattendant ← 나머지. 레포별 deploy key(쓰기 권한), 설정은 ops/README.md
- [x] 레포 공개 범위 결정 (2026-10-06): 두 레포 모두 공개, 비밀값·원본 로그·미발행 초안만 비공개 (architecture.md 저장소 섹션)
- [x] 운영 레포 Public 전환 (2026-10-06). 전환 직전 두 레포 히스토리를 gitleaks 기본 규칙 222개 전체로 검사해 0건 (운영 7커밋, 사이트 1커밋)
- [x] 두 레포 Secret Scanning + Push Protection 켜기 (2026-10-06)
- [x] pre-commit 비밀키 스캐너 (gitleaks 8.30.1, 두 레포 공통 훅 ops/githooks/pre-commit, 2026-10-06). 기록은 docs/pre-commit.md
- [x] 검색엔진 3곳 등록 (2026-10-06)
  - [x] Google Search Console: 도메인 속성, Cloudflare DNS TXT로 인증, sitemap.xml 제출
  - [x] Bing Webmaster Tools: Search Console에서 가져오기 (인증·사이트맵 함께)
  - [x] 네이버 서치어드바이저: HTML 파일 인증(site/static/naver….html), sitemap.xml 제출
  - 인증용 DNS TXT 레코드와 네이버 HTML 파일은 지우지 않는다 (지우면 인증이 풀린다)
- ~~Anthropic API 키 발급하고 월 사용 한도 설정~~ Phase 2 준비로 옮김 (2026-10-06). Phase 1은 Pro 구독으로 돌린다 ([claude-billing.md](claude-billing.md))
- [x] 디스코드 서버와 봇 만들기 (2026-10-06)
  - 서버 `unattendant`, 채널 #긴급 #승인 #일일요약, #긴급에 외부 감시용 웹훅
  - 봇: Public Bot 끔(Install Link None, Guild Install만), Privileged Intents 모두 끔, 권한 View Channels·Send Messages·Embed Links·Attach Files·Read Message History
  - 토큰·웹훅 URL·운영자 ID·채널 ID는 `.env` (600)
  - 확인: REST API로 봇 계정·서버 참여 조회, 채널 3곳 메시지 전송(#긴급 멘션 포함), 웹훅 전송 모두 200

**게이트 1**
- [x] 도메인으로 사이트가 열린다
- [x] 첫 글(사람이 직접 쓴 소개글) 발행 (2026-10-06 20:34): /posts/starting-unattendant/, 영어판 /en/posts/starting-unattendant/ (AI 번역 표시)
- [x] 네이버 서치어드바이저에 RSS(https://unattendant.dev/index.xml) 제출 (2026-10-06, 첫 글 발행 뒤)
- [ ] 첫 글 색인 확인

## 다음 단계 준비

### Phase 1: Pro 구독으로 돌리기 (크레딧 없음)

- [ ] claude.ai Settings → Usage에서 usage credits가 꺼져 있는지 확인. 켜져 있으면 한도를 넘은 사용량이 API 정가로 결제된다
- [x] gitleaks에 Claude Code 구독 토큰 규칙 추가 (2026-10-06): `anthropic-credential`, 테스트 15개 통과. 규칙 추가 전에는 구독 토큰이 그대로 커밋됐다. 실제 토큰 발급 뒤 `.env`를 값을 가린 채 검사해 걸리는지 확인한다 ([pre-commit.md](pre-commit.md) 실험 기록 5)
- [ ] `claude setup-token`으로 1년 토큰 발급 → `.env`의 `CLAUDE_CODE_OAUTH_TOKEN`. 토큰은 터미널에만 한 번 출력되니 바로 저장하고, 만료일을 여기 적는다
- [x] Huninn 전용 `CLAUDE_CONFIG_DIR` 폴더 (2026-10-06): `~/.config/huninn/claude` (700, 레포 밖). 설정·로그인 정보·대화 기록·스킬·플러그인에 전역 설정 `.claude.json`까지 분리되는 것을 확인. 레포의 `CLAUDE.md`는 분리되지 않는다 ([ops/README.md](../ops/README.md))
- [ ] Huninn용 `settings.json` (blogops와 함께): blogops MCP 툴만 허용, `claudeMdExcludes`로 레포 `CLAUDE.md` 제외, auto memory 끄기 검토, 대화 기록 보존 방식
- [ ] 비용 로그: `claude -p --output-format json`의 `total_cost_usd`를 사이클마다 기록하고 `estimate: true`로 표시. Phase 2의 실제 청구 비용과 섞지 않는다
- [ ] Huninn 커밋의 git 작성자를 `Huninn`으로 설정: blogops의 커밋 코드에서 `git -c user.name=Huninn -c user.email=…`로 커밋한다. 커밋 메시지(`content(ai)`)와 작성자가 서로를 검증한다 (CLAUDE.md 커밋 규칙)

### Phase 2: API 크레딧으로 바꾸기

- [ ] Anthropic Console: 크레딧 충전, 조직 월 한도, Huninn 전용 워크스페이스와 월 한도, 서비스 계정, 워크스페이스로 한정한 API 키 (절차는 [claude-billing.md](claude-billing.md))
- [ ] 인증 전환: `.env`의 `CLAUDE_CODE_OAUTH_TOKEN` → `ANTHROPIC_API_KEY`. 구독 토큰은 지운다
- [ ] Phase 1의 추정 비용과 Phase 2 실측 비용을 비교해 모델(Sonnet 5.5 / Opus 5.5)과 워크스페이스 한도를 정한다

## 열린 질문

- 승인 모드 해제 기준(2주 무개입, 첫 통과율 80%)은 제안값이다. 운영하면서 조정한다.
- 가공 운영 지표의 형식과 위치: 원본 로그에서 식별자를 뺀 지표를 공개하기로 했다. 어느 폴더에 어떤 형식(JSONL, CSV)으로 매일 커밋할지는 Phase 2에서 로깅을 만들 때 정한다.
- 승인 기능의 단계: Phase 1은 모든 글을 사람이 승인하는데, 승인 수단인 디스코드 봇(#승인 버튼)은 로드맵상 Phase 2다. (a) Phase 1에 봇의 승인 기능만 먼저 만들기 (제안) 또는 (b) Phase 1은 `state/approvals/`를 손으로 고쳐 승인하고 봇은 Phase 2. Phase 1 시작 전에 정한다.
- 반려 후 처리: #승인에서 반려하면 사유를 받아 다시 고치게 할지, 보류로 둘지 정해져 있지 않다. 승인 기능을 만들 때 정한다.
- 승인 뒤 본문 변경: 품질 검사 뒤 변경은 거부하지만 승인 뒤 변경 규칙은 없다. 승인 기록을 초안 내용 해시에 묶는 방식을 검토한다. 승인 기능을 만들 때 정한다.
- 외부 업타임 모니터(UptimeRobot 등): 설계에는 있지만(architecture.md 알림 섹션) 어느 단계 체크리스트에도 없다. 디스코드 #긴급 웹훅은 만들어 뒀다. 사이트가 떠 있으니 Phase 0에 넣어도 된다.
