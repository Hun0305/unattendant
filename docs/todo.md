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
| Phase 2 · 자율 루프 (C2) | 2\~4주 | API 크레딧 결제 시작. 자체 루프와 예산 상한, 실험 러너(비전·LLM)와 공통 로거, JSONL 로깅, 운영 대시보드, 디스코드 알림. 주간 보고서 자동 발행, 전략 문서 자동 갱신 | 3: 2주 연속 사람 개입 0회, 그 2주 동안 첫 검사 초안 5개 이상에 첫 통과율 80% 이상 → 승인 모드 해제 |
| Phase 3 · 완전 자율과 확장 | 이후 상시 | 자동 발행, 공개 운영 현황 페이지, blog-mcp를 다른 사람도 쓸 수 있게 패키지로 정리(코드는 처음부터 공개), 커뮤니티 배포. WOL로 작업 장비 연동(양자화·오프로딩), 필요하면 SSD 이전·Cloudflare Pages 대기 미러 | — |

## 지난 단계: Phase 0 (기반 준비, 2026-10-06 완료)

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

**게이트 1**: 색인 확인만 남아, Phase 1과 병행하며 기다린다 (조건부 통과, 2026-10-06)
- [x] 도메인으로 사이트가 열린다
- [x] 첫 글(사람이 직접 쓴 소개글) 발행 (2026-10-06 20:34): /posts/starting-unattendant/, 영어판 /en/posts/starting-unattendant/ (AI 번역 표시)
- [x] 네이버 서치어드바이저에 RSS(https://unattendant.dev/index.xml) 제출 (2026-10-06, 첫 글 발행 뒤)
- 첫 글 색인 확인 → Phase 1로 옮김 (기한 2026-10-13)

## 현재 단계: Phase 1 (반자동 루프)

Huninn이 Claude Code(`claude -p`)로 하루 한 번 돌며 글감 선정부터 발행까지 하고, 모든 글은 사람이 승인한다. Pro 구독으로 돌리고 크레딧은 결제하지 않는다. 에이전트 코드는 `feat/` 브랜치에서 만들고 PR로 합친다.

### 먼저 정할 것

- [x] 승인 방식 (2026-10-06 결정): (b) 디스코드 #승인에는 알림만 보내고, 승인과 반려는 Pi에서 명령으로 한다. 폰 승인은 열린 질문
- [x] 반려 후 처리 (2026-10-06 결정): 반려할 때 사유를 남기면 Huninn이 그 사유로 고치고, 고친 초안은 품질 검사를 다시 통과한 뒤 다시 승인을 요청한다. 사람이 승인해야만 발행된다
- [x] 승인 뒤 본문 변경 (2026-10-06 결정): 승인할 때 초안 내용의 해시(지문)를 함께 기록하고, `publish_post`가 발행 직전에 다시 계산해 다르면 발행을 거부하고 다시 승인을 요청한다. 사람이 읽은 버전만 발행된다

### Phase 0에서 넘어온 것

- [ ] 첫 글 색인 확인 (기한 2026-10-13): Google Search Console에서 실제 URL 테스트·색인 생성 요청, 네이버 웹페이지 수집 요청. 기한까지 안 되면 Huninn이 첫 글을 내기 전에 원인부터 찾는다
- [ ] 외부 업타임 모니터(UptimeRobot) → 디스코드 #긴급 웹훅. 업타임 기록을 첫날부터 쌓는다. 설계·설정값·순서는 [uptime.md](uptime.md) (2026-10-13 설계)
  - [x] 설정 (운영자, 2026-10-13 21:37 완료): 계정, 디스코드 연동(#긴급, 멘션 확인), 모니터 1개(홈 키워드), 임시 모니터로 Down·Up 시험, 공개 상태 페이지. 기록 시작 시각(약 21:20)과 상태 페이지 주소는 uptime.md 7절. 남은 확인은 8절
  - [x] 소개 페이지 업타임 문구를 "정상이었던 시간의 비율"로 (2026-10-13, 사이트 레포 `163ffb3`)
  - [x] 통계 탭 "지금 Pi"의 "업타임"을 "가동 시간"으로 (2026-10-13, 사이트 레포 `e6e9a76`). 업타임이 가용률 하나만 가리키게 했다
  - [x] 사이트에 상태 페이지 링크: 통계 탭 지표 설명과 소개 페이지 업타임 행, 한·영 (2026-10-13, 사이트 레포 `3488c41`)
  - [ ] 기록 내보내기 (기한: 모니터를 만든 날 + 3개월 전, 대략 2027-01 초): 무료 플랜은 기록을 3개월만 보관한다. 내용은 [todo_phase2.md](next/todo_phase2.md) 4.3절 "업타임"

### 준비

- [x] claude.ai usage credits 꺼짐 확인 (한도를 넘으면 API 정가로 결제되는 것을 막는다)
- [x] gitleaks에 구독 토큰 규칙 `anthropic-credential` 추가, 테스트 15개 통과. 실제 토큰(`sk-ant-oat01-…`)이 이 규칙에만 걸리는 것을 2026-10-07에 확인 ([pre-commit.md](pre-commit.md) 실험 기록 5)
- [x] `claude setup-token`으로 1년 토큰 발급 → `.env`의 `CLAUDE_CODE_OAUTH_TOKEN` (만료 2027-10-06)
- [x] Huninn 전용 `CLAUDE_CONFIG_DIR` 폴더 `~/.config/huninn/claude` (700, 레포 밖)
- [x] Huninn용 `settings.json` 작성·설치: 원본 `ops/huninn/settings.json` → `ops/install-huninn-config.sh` (설명은 [ops/README.md](../ops/README.md))
- [x] 발급한 구독 토큰이 gitleaks 규칙에 걸리는지 확인 (2026-10-07): `.env`를 값을 가린 채 검사, 토큰 줄이 `anthropic-credential`에만 걸림 (pre-commit.md 실험 기록 5)

### 만들 것

설계와 만드는 순서는 [blogops.md](blogops.md) 9절에 있다. 1~7단계는 모두 끝났다(2026-10-12). 지금은 게이트 2(Huninn이 쓴 글 5편)를 채우는 중이다.

- [x] `state/` 뼈대 (2026-10-07, `feat/blogops` 0fb87d5): `state/strategy.md` 전략 1판(하루 1편 목표, 1인칭 "~다"체), `state/backlog.json` 글감 7개. `state/drafts/`, `state/approvals/`는 공개하지 않으므로 blogops가 처음 쓸 때 만든다
- [x] 1~5단계: blogops 핵심 툴과 MCP 서버 (2026-10-07, PR #1로 main에 합침)
  - [x] 1단계 `store`(초안·승인 기록, 해시, 상태 계산)와 사람용 `review` 명령, 테스트 21개 (2026-10-07)
  - [x] 2단계 `records`(공개 기록 읽기, git log, 발행된 글 목록), `quality`(품질 검사), 테스트 39개 (2026-10-07). 실제 문서·사이트로 검사 1회 4.5초
  - [x] 3단계 `publish`, `backlog`, 테스트 46개 (2026-10-07). 실제 사이트 사본으로 품질 검사 → 승인 → 발행까지 끝까지 확인 (발행 4.6초, pre-commit 훅 통과)
  - [x] 4단계 `notify`(디스코드), `indexnow`, `log`(사이클당 툴 호출 상한), 테스트 54개 (2026-10-07). 실제 디스코드 3채널 전송 확인. IndexNow는 키 파일을 사이트에 배포한 뒤 실제 요청
  - [x] 5단계 MCP 서버와 실행 스크립트 (2026-10-07, PR #1로 main에 squash merge)
    - [x] 작성: MCP 서버(툴 18개), 하루 사이클 실행(`cycle.py`, `run-cycle.sh`), 시스템 프롬프트(`ops/huninn/prompt.md`), 테스트 69개 통과. MCP 프로토콜로 툴 목록·호출 확인
    - [x] 실제 실행 시험 (작업실 `~/unattendant`, 발행 막음): `BLOGOPS_NO_PUBLISH=1 ops/huninn/run-cycle.sh` (먼저 `--show`로 명령만 볼 수 있다. venv는 `agent/README.md` 설치 참고)
      - 01:55 첫 시험: 초안 생성 직후 Pro 세션 한도에 걸려 실패(32초, 툴 7회, 추정 $0.11). #긴급 실패 알림은 정상. 개발 세션과 한도를 나눠 쓰는 문제가 실제로 나왔다
      - 03:47 두 번째: 성공. 41초, 툴 10회(오류 0), 추정 $0.14. 글감 `gitleaks-on-pi`로 초안을 쓰고 품질 검사 첫 시도 통과 → #승인 요청 → #일일요약. 허용되지 않은 도구 시도 0회
      - 시험 초안 `20261007-gitleaks-on-pi`는 작업실에만 있다(승인 대기). 백로그 변경은 되돌렸다. 매장을 만들면 상태는 새로 시작한다
- [x] Huninn 실행 스크립트와 `ops/huninn/mcp.json`: `--tools ""`, `--strict-mcp-config`, `--setting-sources user`, `--no-session-persistence` (ops/README.md 실행 옵션). mcp.json에 서버 이름을 `blogops`로 등록해야 settings.json의 허용 규칙(`mcp__blogops`)과 맞는다 → 2026-10-07 `ops/huninn/run-cycle.sh`(`agent/blogops/cycle.py`). `--model`, `--system-prompt`(prompt.md), `--permission-mode dontAsk`를 더하고 레포 밖 작업 폴더에서 돈다
- [x] 실행 확인: 구독 토큰으로 돌려 레포 `CLAUDE.md`가 빠지는지(`claudeMdExcludes`), blogops 툴만 보이는지
  - [x] 인증, `CLAUDE.md` 제외, 기본 도구 제외, 동기화 스킬·대화 기록 없음 확인 (2026-10-07, ops/README.md). 모델을 안 정하면 Pro 기본 모델(Sonnet 5.5)이 쓰이니 실행 스크립트에 `--model`을 넣는다
  - [x] blogops 툴만 보이는지 (2026-10-07 5단계 실행 시험): blogops 툴만 불렀고 허용되지 않은 도구 시도 0회
- [x] 6단계: 운영 위치 분리와 타이머 (blogops.md 7절). 매장이 생기고 동기화 두 가지가 있어야 타이머를 켠다 → 2026-10-12 완료. 타이머를 켰고 첫 자동 사이클은 2026-10-13 14:00 KST
  - [x] 운영 폴더 분리 (2026-10-12): 두 레포를 `~/unattendant-live`에 clone, 훅 연결, 비밀값을 `~/.config/huninn/huninn.env`로, Caddy 경로 변경과 재시작(sudo, 운영자), CLAUDE.md·architecture.md에 반영
    - [x] 2026-10-12 완료: clone·훅·비밀값(`ops/setup-live.sh`), Caddy가 매장 `site/public`을 서빙(경로 전환·재시작, 응답 200), `claudeMdExcludes`에 매장 경로, `~/.local/bin/review` 연결
    - [x] CLAUDE.md 구조와 architecture.md 디렉터리 구조에 작업실·매장 구분 반영 (2026-10-12)
  - [x] 사이클 시작 동기화 (2026-10-12, PR #2, `agent/blogops/sync.py`·`cycle.py`, 테스트 11개 추가로 80개 통과. 매장 첫 실행에서 `pulled` 기록 확인): 두 레포를 `git pull --ff-only`로 받고, 사이트가 바뀌었으면 다시 빌드한다. 받지 못하면 #긴급으로 알린다
  - [x] 사이클 끝 `state/` 커밋·push (2026-10-12, PR #2. 매장 첫 실행에서 작성자 Huninn 커밋 `c712076`이 GitHub main에 올라감 확인. claude가 실패해도 커밋하고, 동기화 실패 시 사이클을 시작하지 않고 #긴급. 시험 실행 `BLOGOPS_NO_PUBLISH`은 동기화를 건너뜀): Huninn이 바꾼 `state/backlog.json`을 작성자 Huninn으로 운영 레포에 커밋·push한다. 겹치면 rebase 후 한 번 더, 그래도 실패하면 #긴급. 커밋하지 않으면 다음 사이클의 pull이 막힌다
  - [x] systemd 유닛 작성 (2026-10-07): `ops/systemd/huninn-cycle.service`·`.timer`. 매일 14:00 KST, 30분 제한, 쓰기 가능한 곳 제한. 같은 설정을 `systemd-run --user`로 시험해 성공 (15.6초, 메모리 최댓값 312MB). 설치는 [ops/README.md](../ops/README.md) "Huninn 타이머"
  - [x] 매장에서 손으로 한 번 실행 (2026-10-12 19:10): 65초, 툴 10회(오류 0), 추정 $0.16, 메모리 최댓값 427.6MB. 초안 `20261012-gitleaks-on-pi` 품질 검사 통과·승인 대기, state 커밋 push 확인. 발행(git commit·push) 경로는 승인된 글이 없어 이때는 시험하지 못했고, 같은 날 7단계에서 확인했다. 이어서 타이머를 켬(`enable --now`, 다음 실행 2026-10-13 14:00 KST)
  - [x] 메모리 제한 켜기 (2026-10-12): `/boot/firmware/cmdline.txt`에 `cgroup_enable=memory cgroup_memory=1`을 더하고 재부팅. `cgroup.controllers`에 memory가 보이고 Caddy `MemoryCurrent`(56MB)와 `MemoryMax`(200M)가 걸림. 백업 `cmdline.txt.bak`
- [x] 7단계: Huninn의 첫 글 → 게이트 2 시작 (2026-10-12 첫 글 발행)
  - [x] 승인 흐름을 실제로 쓰기 (2026-10-12): #승인 알림 → `review reject`(사유) → 전략 v2로 반영 → `review approve` → 사이클에서 발행까지 한 바퀴. 첫 초안 `gitleaks-on-pi`는 제목이 전문용어뿐이고 문서 요약처럼 읽혀 반려한 뒤 보류(held)로 접고 글감을 `blocked`로 바꿈. 반려된 초안은 다음 사이클이 먼저 고치도록 돼 있어 접으려면 보류가 필요했다(`review`에 보류 명령이 없어 `Store.mark_held`로 직접 처리)
  - 발행에는 승인한 다음 사이클을 기다리지 않고 `sudo systemctl start huninn-cycle`로 당겼다. 반려·승인 직후 자동으로 사이클을 돌리는 것은 구독 한도와 반복 반려 위험 때문에 미룸
  - [x] 첫 발행 커밋이 작성자 `Huninn`, 메시지 `content(ai)`인지 확인 (2026-10-12): 사이트 레포 `9fd2a90`, 작성자 `Huninn <huninn@unattendant.dev>`. 공개 URL 200, 사이클 79초·툴 14회(오류 0)·추정 $0.15
- [x] 매장 정리 (6단계 뒤 남은 잔일, 2026-10-12 완료)
  - [x] 작업실 `.env` 지우기 (2026-10-12): 키 7개와 값이 `~/.config/huninn/huninn.env`와 모두 같은 것을 확인한 뒤 삭제. 작업실에서도 `huninn.env`를 읽는다. 새 비밀값은 `huninn.env`에만 넣는다
  - [x] 터널 설정 경로를 매장으로 (2026-10-12, `12d06b0`): `unattendant-tunnel.service`의 `--config`를 `~/unattendant-live/ops/cloudflared/config.yml`로 바꿨다(`tunnel ingress validate` OK). 운영자가 유닛을 설치하고 재시작했고, 서비스가 매장 설정으로 active, https://unattendant.dev 200 확인
- [x] 그림 포함 글의 첫 자동 발행 확인 (2026-10-13 14:00 사이클): `ai-site-first-screens`가 승인된 상태. 그림 2개 복사, 커밋 메시지의 "그림 2개", 공개 URL의 그림 접근, 새 초안의 그림 제안(전략 v3)을 확인한다
  - 결과: 사이트 레포 `3d7ff5f`(작성자 Huninn, `content(ai)`), 커밋 본문에 "그림 2개: first-screens-map.svg, home-e.png", 글 폴더에 두 파일 복사, 공개 URL 글·그림 둘 다 200. 사이클 성공(툴 13회·오류 0, 추정 $0.24), state 커밋 `81117ed` push
- [ ] IndexNow 실제 사용 (뒤로 미룸, 2026-10-07 결정): 키 파일 `site/static/<키>.txt`를 사이트 레포에 커밋·배포한 뒤 첫 소개글로 실제 색인 요청. 그 전까지 `request_indexing`은 키가 없다고 알리고 건너뛴다. 방법은 [indexnow.md](next/indexnow.md)
- [x] 비용 로그: `claude -p --output-format json`의 `total_cost_usd`를 사이클마다 기록하고 `estimate: true`로 표시 (Phase 2 실제 청구와 섞지 않는다) → 2026-10-07 `cycle.py`가 `logs/cycles.jsonl`에 남긴다(모델별 사용량 포함). `get_week_summary`가 주간 합계를 쓴다

### 사이트

- [ ] Pi 상태 표시 (2026-10-14, Phase 2에서 앞당김): 상태 띠와 통계 탭이 지금 Pi의 CPU 온도·메모리·디스크 여유·가동 시간을 보이게 한다. 무인 운영 전에도 돈다. 설계는 [status.md](status.md)
  - [x] `agent/blogops/status.py`와 테스트 12개 (`feat/status-json`): 5분마다 `/run/huninn/status.json`(RAM)에 쓴다
  - [x] 서비스·타이머 유닛(`ops/systemd/huninn-status.*`)과 Caddy `/status.json` 경로. 임시 Caddy로 상태 파일 경로 말고는 옛 설정과 같은 응답인 것을 확인
  - [x] 사이트(사이트 레포): 상태 띠에 메모리 칸, 연속 무인 운영일이 없는 동안 "운영 준비 중"을 값과 함께 둠. 헤드리스 Chromium으로 네 경우 확인
  - [ ] PR 병합, 매장 pull, 설치(sudo: 유닛 설치, 타이머 켜기, Caddy 재시작), 공개 URL과 브라우저에서 확인. 순서는 [ops/README.md](../ops/README.md) "Pi 상태 파일"
  - [ ] 나중에: `unattended_days`·`cost_today_krw` 필드(아래 Phase 2), 경고 색(`state`)
- [x] 글에 그림 넣기 (2026-10-12, 사이트 레포 `3479e2e`·`f2bf6ec`): `fig` 단축 코드(SVG는 본문에 넣어 다크 모드를 따름), 이미지 규칙을 "측정 그래프만"에서 "누가 만들었는지 밝히고, 남의 그림은 퍼블릭 도메인·허락된 것만, 그림당 200KB 이내"로 바꿈(site/README.md). 첫 글 `name-given-to-me`에 신화 삽화(SÁM 66, 퍼블릭 도메인)와 SVG 두 장을 직접 넣었다
- [x] 전략 v3 "시각자료" 절: 글마다 1~3개, 그래프 → 다이어그램 → 사진·도판(출처 표기) → AI 그림(밝히기) 순. 지금 Huninn은 그림을 받거나 만들 수 없어 #일일요약 "그 밖에"에 그림 제안만 적는다
- [ ] Huninn이 쓰는 글에 그림 넣기 (blogops 지원, 2026-10-12 운영자가 만들고 싶다고 함)
  - [x] 최소 지원 (2026-10-12, PR #3 `a351857`): 초안 폴더의 그림(svg·png·jpg·webp·gif)을 승인 해시에 포함, 발행 때 글 폴더로 복사, 품질 검사(`fig`와 파일 일치, `caption` 필수, 래스터는 `alt` 필수, 파일당 200KB, SVG의 `<script>`·외부 참조 금지), `review show`에 그림 표시. 사이트 README의 "이미지는 측정 그래프만" 규칙은 "누가 만들었는지 밝히면 가능"으로 바꿈. 지금은 운영자가 파일을 넣고 본문에 `fig`를 쓴다 (`ai-site-first-screens`가 첫 사례)
  - [ ] Huninn이 직접 그림 자리를 제안하고 SVG를 만들기: 지금 Huninn은 그림을 받거나 만들 수 없다. 초안에 SVG를 함께 올리는 툴(예: `add_figure`)을 만들어 다이어그램은 Huninn이 직접 그리게 한다. 사진·AI 그림은 계속 제안만(운영자가 준비) 또는 이미지 생성 도구를 붙일지 따로 정한다
  - [ ] AI가 만든 그림 표시를 구조화: 지금은 캡션 문장으로만 밝힌다. front matter나 `fig`의 `by`(human·ai·pd) 속성으로 받아 글 하단에 "그림 출처" 목록을 자동으로 만들고, 품질 검사에서 `by` 누락을 잡는다
  - [x] 그림 제안 방식 점검 (2026-10-13 사이클): 일일요약 "그 밖에"에 "요청 흐름 다이어그램과 3안 비교표"를 제안했고 초안에도 적었다. 전략 v3대로 동작

- [x] 상태 띠 링크 문구 "라즈베리파이 한 대에서 돌아갑니다 →" 고치기 (`site/i18n/ko.toml`의 `bandLink`, 영어판 `en.toml` "Running on a single Raspberry Pi"도 함께) → 2026-10-12 고치지 않고 링크째 삭제(통계 탭 메뉴와 겹침). 같은 날 메뉴 "숫자" 탭 이름을 "통계"로 바꿈(주소 `/numbers/`는 유지)
- [x] 블로그 페이지 디자인 다듬기: 사람이 읽고 싶은 화면으로. 홈 글 목록, 글 본문(글꼴, 글 폭, 줄 간격, 제목 위계, 표·코드·그림), 모바일, 다크 모드를 본다. 레이아웃 구조는 E안 그대로 ([layout-options.md](layout-options.md)) → 2026-10-12 데이터시트형(IBM Plex Sans KR·Mono, 기판 초록 상태 띠, 가로 괘선 표)으로 바꿔 배포. 기준과 결정 경위는 사이트 레포 `DESIGN.md`
- [x] (친구 피드백, 2026-10-07) 어떤 AI 모델을 쓰고 자동화 파이프라인을 어떻게 짰는지 명시. 지금 첫 글 "두뇌" 부분은 "Claude. 처음에는 Claude Code를 스크립트로…"뿐이다
  - 모델: 정확한 모델 이름과 버전, effort, 인증 방식(Phase 1 Pro 구독 → Phase 2 API). 모델은 실행 스크립트 기본값 `claude-sonnet-5-5`로 정해졌다(`agent/blogops/cycle.py`, 2026-10-07)
  - 파이프라인: systemd 타이머 → `claude -p` → blogops MCP 툴(초안 → 품질 검사 → 승인 요청 → 발행) → Hugo 빌드 → 공개 URL 확인 → 색인 요청. 그림 하나로 보여준다
  - 어디에: 첫 글 "두뇌" 부분 보강(수정일 표시), 소개 페이지, 글마다 쓴 모델을 글 하단에 표시할지 검토
  - 완료 (2026-10-12, 사이트 레포 `317fe80`·`7e93899`·`0783aeb`): 첫 글 "두뇌"를 "Huninn은 어떻게 돌아가나" 소절로 교체(모델 `claude-sonnet-5-5` 고정, effort 미설정, `claude -p`, Pro 구독과 추정 비용, blogops 툴 18개, 하루 사이클 그림, 한도 표, 개발에 쓴 Claude Code). 소개 페이지에도 모델 설명 추가. 영어판도 같은 내용, 글 끝에 수정 기록
  - 남음: 글마다 쓴 모델을 글 하단에 표시할지는 검토하지 않았다(레이아웃에 모델 표시 없음)
- [x] (친구 피드백, 2026-10-07) 첫 글 성공 기준 1 "사람 개입 없이 4주 이상 연속 운영"에서 무인 운영의 기준을 정확히 정의
  - 무엇이 "개입"인지: 승인·반려, 초안 수정, 서비스 재시작, 설정·코드 수정, 보안 업데이트(`apt upgrade`), 토큰 갱신 같은 경우를 하나씩 정한다. 설계 문서는 지금 "수동 승인을 제외한 수동 조작·수정"뿐이다
  - 4주를 언제부터 세는지: 승인 모드 해제(게이트 3) 뒤부터인지, 개입이 한 번 생기면 0일부터 다시 세는지
  - 장애가 났지만 자동 복구된 날은 무인 운영일로 치는지
  - 정한 정의를 첫 글(수정일 표시), 숫자 탭(`/numbers/`), architecture.md 지표 표에 같은 문장으로 맞춘다. 개입 로그도 이 정의대로 기록한다
  - 완료 (2026-10-12, 사이트 레포 `317fe80`·`7e93899`): 정의는 소개 페이지 "무인 운영의 기준"에 정했다. 개입은 "Huninn이나 시스템이 혼자 못 해서 사람이 대신하거나 바로잡은 일"(승인과 계획된 개발은 제외, 장애를 고치는 변경은 개입), 4주는 "승인 모드를 끈 뒤 연속 28일"(개입이 생기면 0부터), 장애는 24시간 안에 사람 없이 복구되면 날수를 끊지 않음. 첫 글(한·영)에 같은 기준을 반영
  - 문서 맞춤 (2026-10-13): 숫자 탭 `/numbers/`(한·영)와 architecture.md 성공 기준·지표 표(연속 무인 운영일, 사람 개입 횟수)를 같은 정의로 고쳤다. 숫자 탭은 소개 페이지 "무인 운영의 기준"으로 링크하고 사이트 레포 `f39f02e`에 있다. architecture.md 변경은 아직 커밋 전
  - 개입 로그 기록은 정의가 아니라 구현이라 Phase 2 항목으로 옮겼다

### 다음에 만들고 싶은 것 (2026-10-12 운영자 아이디어)

- [ ] 반려되면 그 자리에서 다시 쓰고 다시 승인 받기: 지금은 반려해도 다음 사이클(최대 하루 뒤)에야 고친다. 반려 직후 바로 재작성하고 품질 검사 → 승인 요청까지 이어 가게 한다
  - 결정 (2026-10-13): 반려와 접기 둘 다 사이클을 바로 돌린다. 하루 5회 상한. 승인은 돌리지 않는다(승인한 글은 다음 14:00에 발행)
  - [x] 코드 (2026-10-13, `feat/discord-approval`, 아직 PR 전): `ondemand.py`(요청 파일 `logs/.cycle-request` 하나만 쓴다, 하루 5회 상한, path 유닛이 그 파일을 지켜볼 때만 요청), `ops/systemd/huninn-cycle-now.path` + `huninn-cycle.service`의 `ExecStartPre`, `decisions.next_step`으로 디스코드 응답·#승인 결과 메시지·`review` 출력 문구 통일, 프롬프트 한 줄. 봇에 서비스 시작 권한(polkit)을 주지 않는다. 테스트 165개 통과. 설계는 [blogops.md](blogops.md) 12절
  - [x] 확인 (2026-10-13): 사용자 매니저의 임시 유닛으로 systemd 동작(요청 1번=1번 실행, 실행 중 요청=끝난 뒤 1번 더, 연속 3번=1번)과 실제 `ondemand.request`의 파일 쓰기 → 서비스 시작(1.5초)을 확인. 시스템 유닛 설치는 아직 하지 않았다
  - [ ] 운영 반영 (운영자, sudo): 매장 `git pull` 뒤 `sudo install`로 `huninn-cycle.service`·`huninn-cycle-now.path`를 설치하고 `enable --now huninn-cycle-now.path`. 유닛을 켜기 전에는 "다음 14:00 사이클에서"라고 안내한다. 첫 확인은 실제 반려 1번(사이클이 돌아 구독 한도를 쓴다). 명령은 [ops/README.md](../ops/README.md) "반려·접기 직후 바로 쓰기"
  - 소재도 바꿀지 정해야 한다. 반려 사유가 "글을 고치라"인지 "이 주제를 접으라"인지에 따라 다르다. 이번에 `gitleaks-on-pi`는 후자였는데 `review`에 폐기·보류 명령이 없어 `Store.mark_held`로 직접 보류하고 백로그를 손으로 `blocked`로 바꿨다. `review reject --drop`처럼 접는 반려와 글감 상태 변경을 한 번에 하는 명령이 필요하다 → 2026-10-13 만들었다(`review reject --drop`, 디스코드 [접기] 버튼. `feat/discord-approval`). 바로 재작성은 아래에서 했다
  - 구현 후보(→ polkit 대신 systemd path 유닛으로 구현했다. 아래): `review reject` 뒤에 사이클을 바로 한 번 더 돌린다(`systemctl start`는 root가 필요하니 polkit·sudoers 허용이 필요). 위험: 구독 한도(개발 세션과 공유, 5단계 첫 시험에서 한도에 걸린 적 있음), 반려 → 재작성 → 반려 반복(하루 재실행 횟수 상한 필요), 시스템 설정 변경이라 운영자 승인 필요
- [ ] 디스코드에서 초안을 읽고 승인·반려하기 (폰에서): 지금 승인은 Pi에서 `review` 명령으로만 가능하다. 열린 질문 "폰에서 승인하기"를 구체화한 것
  - 결정 (2026-10-13): 초안 보기는 (b) 미리보기 페이지로 하고 접근은 **토큰 주소만** 쓴다(Cloudflare Access는 겹치지 않는다. 한 번 읽으면 되고 승인되면 어차피 공개될 글). 사이트 전체를 빌드해 메뉴 이동까지 된다. 버튼은 게이트웨이 방식 봇. 설계와 근거는 [blogops.md](blogops.md) 11절
  - [x] 코드 (2026-10-13, 브랜치 `feat/discord-approval`, 아직 PR 전): `preview.py`(미리보기 빌드), `buttons.py`, `decisions.py`(승인·반려·접기), `bot.py`(discord.py 2.7), `notify.py`(링크·버튼 부착, 결정 뒤 메시지 정리), `review preview`·`reject --drop`. 테스트 88개 → 138개 통과. `.gitignore`·pre-commit 훅에 `state/previews/` 추가(훅 테스트 16/16)
  - [x] 확인 (2026-10-13): 실제 사이트와 실제 승인 대기 초안으로 미리보기 빌드 1초, 임시 Caddy(18081)로 헤더·경로 탈출·읽기 전용·글꼴·CSS 확인, 봇 게이트웨이 접속(`--check`, 권한 인텐트 없이) 성공. 상세는 [ops/README.md](../ops/README.md)
  - [x] 실제 디스코드 시험 (2026-10-13 20:36): 가짜 초안 3개를 #승인에 보내고 임시 봇으로 운영자가 폰에서 승인(확인 → 확정)·반려(사유 입력창)·접기(사유 입력창)를 눌렀다. 모두 기록(`via: discord`), 원본 메시지가 결과로 바뀜, 미리보기 삭제, 접기는 초안 held + 글감 blocked. 오류 0. 승인 확인 창의 [취소]만 로그가 없어 미확인
  - [ ] 운영 반영 (운영자, sudo): PR 머지 → 매장 `git pull` → 매장 venv에 `pip install -e ".[bot]"` → `cloudflared tunnel route dns` → Caddy·터널 재시작 → `huninn-bot` 설치·시작. 순서와 명령은 ops/README.md "초안 미리보기 호스트", "Huninn 봇". 매장이 새 코드를 받은 뒤 첫 승인 요청 전에 봇을 켜 둘 것
  - [ ] 폰에서 미리보기 링크 확인 (운영 반영 뒤): LTE에서 열리는지, 다크 모드·그림·영어판·메뉴 이동. 버튼 쪽은 위 실제 디스코드 시험으로 확인했다
  - #승인 알림에 승인·반려 버튼. 반려를 누르면 사유 입력창이 뜨고, 제출하면 반려 기록(`review reject`와 같은 기록)이 남고 위 항목대로 초안 재작성이 시작된다
  - 초안 보기: (a) 디스코드 임베드에 본문 앞부분과 그림 (2000자 제한, 길면 잘림) (b) 공개되지 않는 주소의 미리보기 페이지를 만들어 링크로 보기. (b)는 로그인 없는 추측 불가 토큰 주소, Cloudflare Access(이메일 인증), Tailscale 안에서만 열리는 주소 중에서 고른다. 초안은 비공개 자료라(`state/drafts/`) 공개 도메인에 그냥 열면 안 된다. 그림도 같이 보여야 한다
  - 버튼을 받으려면 디스코드 봇이 상주해야 한다(Interactions를 웹훅으로 받거나 게이트웨이 접속). 지금은 알림만 REST로 보내고 상주 프로세스가 없다. 메모리와 상시 서비스 추가(`MemoryMax`), 봇 권한과 승인 사칭 방지(운영자 ID 확인, 승인 해시 대조 유지)를 설계에 넣는다

**게이트 2**
- [ ] Huninn이 쓴 글 5편 발행 (2/5, 2026-10-13): 1. "내 이름 Huninn은 어떻게 정해졌나" (`name-given-to-me`, 2026-10-12) 2. "AI가 운영하는 사이트들은 첫 화면에 무엇을 보여줄까" (`ai-site-first-screens`, 2026-10-13 14:00, 첫 자동 사이클 발행). 다음은 승인 대기 중인 `pi-blog-no-open-ports`
- [ ] 품질 게이트 통과율 기록 시작 (지금까지 초안 4개 모두 첫 검사 통과, 반려 1건은 내용이 아니라 주제·제목 문제였음)

## 열린 질문

- [ ] 승인 모드 해제 기준(14일 무개입, 그 14일 동안 첫 검사 초안 5개 이상, 첫 통과율 80% 이상)은 제안값이다. 운영하면서 조정한다.
- [ ] 가공 운영 지표의 형식과 위치: 원본 로그에서 식별자를 뺀 지표를 공개하기로 했다. 어느 폴더에 어떤 형식(JSONL, CSV)으로 매일 커밋할지는 Phase 2에서 로깅을 만들 때 정한다. 추천안은 Phase 2 "먼저 정할 것" 4번.
- [x] ~~폰에서 승인하기~~ 결정 (2026-10-13): Phase 2를 기다리지 않고 Phase 1 중에 만든다. 미리보기 링크 + #승인 버튼 + 상주 봇. "다음에 만들고 싶은 것"의 같은 항목에서 진행 상황을 본다.
- [ ] 전력 측정: Pi 4B는 소비 전력을 스스로 읽지 못해 외부 측정기(기록되는 USB 전력계 등)가 필요하다. 살지, 아니면 온도·클럭만 잴지.
- [ ] 네이버 검색 통계: 서치어드바이저 통계를 API로 받을 수 있는지. 안 되면 대시보드에 링크만 둔다.
- [ ] API 잔액: 잔액을 조회하는 공식 방법은 확인하지 못했다(문서에서 확인한 건 Admin 키가 필요한 사용량·비용 보고서뿐이다). 없으면 이번 달 비용 대 한도로 대신한다.
- [ ] C2 루프를 게이트 3 측정 창 앞에 둘지: 추천은 계획대로 C2 먼저다. 승인 모드를 끈 뒤에 루프를 바꾸면 새 코드의 첫 실행부터 사람이 글을 읽어 주지 않는다. C3에 API 키만 바꾼 채로 측정 창을 먼저 돌리면 약 2주 빨리 판정할 수 있지만 그 위험을 진다. API 전환 1주 실측에서 C2의 이득(비용, 메모리, 통제)이 작게 나오면 다시 정한다.
- [ ] 댓글 기능: 넣을지와 방식(giscus vs Pi 자체 서버)은 [comments.md](next/comments.md)에서 비교했다. 악성 사용자를 어떻게 막을지(인증 수준, 스팸 필터, 바로 게시 vs 승인 후 게시)를 먼저 정한 뒤 도입한다. Huninn이 댓글을 읽게 할지는 따로 정한다.

## 다음 단계: Phase 2 (자율 루프, C2)

계획 초안(2026-10-07)을 코드·문서·실행 기록과 대조해 고쳐서 합쳤다(2026-10-13). 설계 근거는 [architecture.md](architecture.md)에 있다. Phase 2를 시작할 때 "시작 조건"과 "먼저 정할 것"을 다시 보고, 이 절을 "현재 단계"로 옮긴다.

### 한눈에

Phase 2가 끝나면 이렇게 돈다.

- Huninn은 `claude -p` 대신 Messages API를 직접 부르는 자체 루프(C2)로 돈다. 비용은 API 기준으로 남고, 사이클·하루·월 예산 상한은 코드가 지킨다.
- 승인 모드는 그대로 켜져 있다. 운영자는 폰에서 디스코드 #승인의 미리보기 링크와 버튼으로 승인·반려한다.
- Pi가 등록된 실험을 밤에 돌리고, Huninn은 그 결과로 실험 글을 쓴다. 소형 LLM이 먼저, 비전이 그다음이다.
- 운영 지표(개입, 장애, 품질 첫 통과율, 비용, 업타임)가 매일 계산돼 공개되고, 상태 띠와 통계 탭이 실제 값을 보여 준다.
- 게이트 3을 판정할 기록이 쌓인다. 통과하면 승인 모드를 끄고 Phase 3(자동 발행)로 간다.

| Phase 2에서 한다 | Phase 3 이후로 미룬다 |
| --- | --- |
| API 크레딧 전환, C2 루프와 예산 상한 | 승인 모드 해제와 자동 발행 (게이트 3 통과 뒤) |
| 운영 지표와 개입 기록, status.json, 로그 백업 | 공개 운영 현황 페이지 |
| 디스코드 봇 (승인 버튼, Phase 1 쪽에서 먼저 구현) | blog-mcp 패키지화, 커뮤니티 배포 |
| 실험 러너와 공통 로거, 첫 실험 글 (LLM → 비전) | WOL 작업 장비 연동(양자화·오프로딩), GPIO 지연 실험, 파인튜닝 |
| Phase 1에서 미룬 툴 (관측, 트렌드, 실험, 공유, 전략 갱신) | SSD 이전, Cloudflare Pages 대기 미러 |
| 비공개 운영 대시보드, 주간·월간 루프 | |

### 시작 조건

Phase 2는 Phase 1이 만든 것 위에 선다. 아래가 끝나야 시작한다.

- [ ] 게이트 2: Huninn이 쓴 글 5편 발행, 품질 첫 통과율 기록 시작 (2/5, 위 "게이트 2")
- [ ] 매장 분리와 14:00 타이머가 며칠 동안 문제없이 돈다. 첫 자동 사이클은 2026-10-13에 성공했다(1회). C2 루프는 같은 서비스(`huninn-cycle.service`) 자리에 들어간다
- [x] Huninn이 운영 레포에 커밋·push하는 길 (2026-10-12, PR #2). 전략 갱신, 지표, 실험 결과도 이 길로 나간다
- [ ] 외부 업타임 모니터 → #긴급 웹훅 (위 "Phase 0에서 넘어온 것"). 업타임과 장애 자동 복구율의 출처다
- [x] "사람 개입"과 무인 운영의 정의 확정 (2026-10-12 소개 페이지 "무인 운영의 기준", 2026-10-13 통계 탭(사이트 레포 `f39f02e`)과 architecture.md(커밋 전)를 같은 정의로 맞춤). 기록하는 코드는 아래 "운영 지표, 개입 기록, 백업"
- [x] 메모리 cgroup 켜기 (2026-10-12): `MemoryMax`가 실제로 걸린다. 위 6단계 참고

### 먼저 정할 것

추천을 적었다. 정하면 날짜와 함께 이 표와 해당 설계 문서에 남긴다.

| # | 정할 것 | 추천 | 이유 |
| --- | --- | --- | --- |
| 1 | 루프 구현 | Messages API 수동 루프 (`stop_reason`으로 분기). SDK Tool Runner(beta)는 쓰지 않는다 | architecture.md가 고른 C2 그대로다. 요청마다 예산 검사, usage 기록, 대화 기록 덧붙이기를 직접 지킨다. beta 의존이 없다 |
| 2 | 모델과 effort | `claude-sonnet-5-5` 유지. effort를 명시하고 `medium`에서 시작 | Sonnet 5.5의 기본 effort는 `high`이고, 툴을 여러 번 쓰는 작업은 `medium`부터 재 보는 것이 권장이다. API 전환 뒤 1주 실측으로 `low`·`high`, Opus 5.5와 비교해 정한다. Opus 5.5는 단가가 2배($4/$20)라 같은 토큰이면 사이클 비용도 약 2배다 |
| 3 | 예산 상한 (제안값) | 코드: 사이클 $1, 하루 $2, 월 $25. Console 워크스페이스 한도: 월 $30 | 실측(2026-10-12~13, 5회, 정가 기준 추정)은 사이클당 $0.02~0.36, 평균 $0.19로 한 달 약 $6~10이다. 사이클 $1은 최댓값의 약 3배, 하루 $2는 4회 돈 10-12($0.69)의 약 3배다. 코드가 먼저 멈추고 Console 한도는 마지막 장치다. 2주 실측 뒤 조정한다 |
| 4 | 가공 운영 지표의 형식과 위치 | 운영 레포 `metrics/daily.csv`(하루 한 줄)와 `metrics/interventions.csv`(사람이 한 일 한 줄씩). 매일 커밋 | GitHub이 CSV를 표로 보여 주고, 누구나 내려받아 다시 계산할 수 있다. 원본 `logs/`는 그대로 비공개다 |
| 5 | status.json 위치 | **결정(2026-10-14)**: `/run/huninn/status.json`(tmpfs)에 쓰고, Caddy가 `:8080`과 미리보기 `:8081`의 `/status.json`만 그 파일로 내준다. `Cache-Control: no-store`. 쓰는 부분은 Phase 1로 앞당겼다 ([status.md](status.md)) | 빌드(`--cleanDestinationDir`)가 `public/`을 비운다 (blogops.md 5절). 5분마다 쓰는 파일이라 RAM에 두면 SD카드 쓰기가 없고, 재부팅하면 비워져도 타이머가 부팅 1분 뒤 다시 쓴다 |
| 6 | 폰 승인 방식 | (2026-10-13 결정, 코드·시험은 끝나 PR·운영 반영 전) #승인 메시지에 미리보기 링크(추측할 수 없는 토큰 주소)와 [승인]·[반려]·[접기] 버튼. Pi의 `review` 명령은 그대로 둔다 | 폰에서 발행될 모습 그대로 읽고 바로 누를 수 있다. 봇이 멈춰도 승인할 길이 남는다. 설계는 [blogops.md](blogops.md) 11절 |
| 7 | 대시보드 접근과 역할 | Tailscale 주소에만 붙이고(Tailscale 설정은 바꾸지 않는다), 승인은 하지 않는 읽기 전용으로 시작 | 대시보드는 터널로 열지 않는다. 지금 인터넷에서 닿는 비공개 경로는 토큰 주소 미리보기 하나뿐이다. 승인 경로는 버튼과 `review` 둘이면 된다. architecture.md는 대시보드에서도 승인을 처리한다고 적었으니 정하면 고친다 |
| 8 | 전략 자동 갱신의 범위 | 주 1회(일요일), 근거 필수. "글을 쓸 때"의 금지 항목 같은 고정 절은 바꿀 수 없다 | 발행 한도와 예산은 전략이 아니라 코드라서, 전략이 바뀌어도 안전장치는 그대로다 |
| 9 | 게이트 3 측정 창 | 사이클 경로(루프 코드, blogops 툴, 프롬프트, 모델)를 바꾸면 14일을 다시 센다. 사이트, 대시보드, 실험 템플릿 변경은 다시 세지 않는다 | 승인 모드를 끄는 근거는 실제로 혼자 돌 그 시스템의 2주여야 한다. 채택하면 소개 페이지 "승인 모드와 성공 기준"과 첫 글에도 한 줄 더한다(지금 공개 기준에는 이 조건이 없다) |

### 만드는 순서

Phase 1의 blogops처럼 설계 문서를 먼저 쓰고 만든다. 게이트 3까지 꼭 거쳐야 하는 길은 굵게 표시했다(API 전환 → 지표·개입 기록 → C2 루프 → 측정 창). 봇, 실험, 대시보드는 그 옆에서 병행한다.

| 순서 | 할 일 | 끝난 기준 |
| --- | --- | --- |
| 0 | 비공개 기록 백업과 업타임 모니터 (앞당김) | `state/drafts/`, `state/approvals/`, `logs/`가 SD카드 밖에도 있고, 사이트가 내려가면 #긴급으로 온다. 지금은 SD 한 벌뿐이라 Phase 2를 기다리지 않는다 |
| 1 | **API 전환** (C3 그대로, 인증만 바꾼다) | 14:00 사이클이 API 키로 돌고, 개발 세션의 Pro 한도와 더는 나눠 쓰지 않는다. 1주 실측 비용이 남고, 이 실측이 "먼저 정할 것" 2·3번의 근거다. `claude -p`의 `--max-budget-usd`·`--effort`로 사이클 상한과 effort를 이 단계부터 건다 |
| 2 | 설계 문서: `docs/loop.md`(C2 루프, 예산, 기록), `docs/experiments.md`(러너, 템플릿, 측정 원칙) | 두 문서가 main에 있고 "먼저 정할 것"이 정해졌다 |
| 3 | **지표·개입 기록**, status.json | 지표가 매일 계산돼 커밋되고, 상태 띠가 실제 값을 보여 준다 |
| 4 | **C2 루프** | 작업실 시험 → C3와 비교(비용, 툴 호출 수, 결과) → 매장 타이머 전환. 1주 동안 실패 없이 돈다 |
| 5 | 디스코드 봇 | 폰에서 승인·반려가 되고, 해시가 다르면 거부되는 것을 확인. Phase 1 쪽 `feat/discord-approval`에서 먼저 만들었다(PR·운영 반영 전) |
| 6 | 실험 러너와 LLM 첫 실험 | 야간 실험 → 결과 CSV 커밋 → 첫 실험 글이 수치 대조 품질 검사를 통과 |
| 7 | 관측·트렌드·공유 툴, 대시보드, 주간 루프 확장 | 주간 보고서에 방문·검색 통계와 실제 비용이 들어가고, 전략 갱신이 한 번 돈다 |
| 8 | 비전 실험(카메라 준비, 정기 촬영, 첫 비전 글), 월간 루프 | 기준 실험을 다시 돌려 기존 글을 갱신. 월간 루프는 프롬프트와 툴을 바꾸므로 측정 창 뒤로 미루고, 템플릿·촬영 준비만 측정 창과 병행한다 |
| 9 | **게이트 3 측정 창** (14일) | 게이트 3 기준을 넘으면 승인 모드 해제를 결정 |

일정(추정): 측정에 걸리는 시간만 API 실측 1주, C2 무실패 1주, 측정 창 14일로 4주다. 개발 시간과, 측정 창 전에 사이클 경로를 바꾸는 일(실험·관측 툴, 프롬프트, 주간 루프)을 모두 끝내야 하는 조건을 더하면 6~8주로 본다. 로드맵 표의 "2\~4주"와 맞지 않는다.

### 할 일

#### API 크레딧 전환

Console 절차는 [claude-billing.md](claude-billing.md) "Phase 2 준비: Console 설정 절차"에 있다.

- [ ] Console: 크레딧 충전, 조직 월 한도, 워크스페이스 `unattendant`와 월 한도·알림, 서비스 계정 `huninn`, 워크스페이스로 한정한 API 키 (만료일 지정)
- [ ] 키를 화면에 남기지 않고 비밀값 파일 `~/.config/huninn/huninn.env`(600)에 넣는다. 만료일은 이 문서에 적는다
- [ ] gitleaks 확인: `anthropic-credential` 규칙이 이미 `sk-ant-api03-`·`admin01-` 형식을 잡는다(ops/gitleaks.toml). 실제 키가 걸리는지 값을 가린 채 한 번 확인한다 ([pre-commit.md](pre-commit.md) 실험 기록 5와 같은 방법)
- [ ] `cycle.py`가 구독 토큰 대신 `ANTHROPIC_API_KEY`를 넘긴다. 지금은 `CLAUDE`·`ANTHROPIC_`로 시작하는 변수를 모두 빼고 구독 토큰만 넘긴다(`claude_env`)
- [ ] `ops/huninn/settings.json`의 `forceLoginMethod`를 `claudeai`에서 `console`로 바꾸고 `ops/install-huninn-config.sh`로 다시 설치한다. API 키로 `claude -p`가 도는지 작업실에서 먼저 시험한다
- [ ] 사이클 상한을 이 단계부터 건다: `claude -p --max-budget-usd`(사이클)와 `--effort`(둘 다 `claude` 2.1.289 도움말에 있다). 하루·월 상한은 `cycle.py`가 `cycles.jsonl` 누적을 보고 실행 전에 막고 #긴급으로 알린다
- [ ] `cycles.jsonl`에 청구 방식(예: `billing: api`)을 남긴다. `total_cost_usd`는 API 키로 돌려도 Claude Code가 정가로 계산한 값이라 `estimate: true`를 유지한다(지금까지 5회 기록이 Sonnet 5.5 단가표로 계산한 값과 소수 넷째 자리까지 같다). Console 사용량과 1주 대조해 오차가 작을 때 `estimate: false`로 바꾼다
- [ ] 비밀값 파일에서 `CLAUDE_CODE_OAUTH_TOKEN`을 지운다
- [ ] 1주 실측을 Phase 1 추정치와 비교해 모델, effort, 한도를 정한다 ("먼저 정할 것" 2·3번)
- [ ] 주 1회 Console 사용량과 로그 합계를 대조한다. 차이가 크면 비용 계산부터 고친다. Pi에는 Admin API 키를 두지 않으므로(조직 관리 권한이라 유출되면 피해가 크다) 대조는 사람이 Console에서 한다

#### C2 루프와 예산 상한

설계는 `docs/loop.md`에 먼저 쓴다. 핵심은 architecture.md 권장 조합대로 툴 로직을 blogops 하나에 두고, MCP 서버와 C2 루프가 같이 쓰는 것이다.

**툴 공유**

- [ ] 툴의 이름·설명·입력 스키마와 호출 검사·기록(`CycleGuard`, `logs/YYYY-MM-DD.jsonl`)을 한 곳에 둔다. 지금은 `server.py`의 `@tool` 데코레이터가 검사·기록 래퍼와 MCP 등록(`server.add_tool`)을 한 번에 한다. 래퍼는 그대로 쓰고 등록만 분리해 레지스트리로 만들면 MCP 서버와 C2 루프가 같이 쓸 수 있다
- [ ] MCP 서버는 남긴다. 운영자가 Claude Code 등에 붙여 손으로 운영할 때 같은 툴과 같은 검사를 쓴다

**요청과 대화 기록** (Sonnet 5.5 기준. claude-api 스킬 문서(2026-10-06 캐시)와 대조해 확인)

- [ ] `anthropic` Python SDK를 의존성에 더한다(지금 `agent/pyproject.toml`에는 `mcp`뿐이다). 루프는 가칭 `agent/blogops/loop.py`
- [ ] `model`과 `output_config.effort`를 늘 명시한다. thinking은 기본(adaptive)을 쓴다. 이 모델에서 `thinking: {"type": "disabled"}`와 강제 `tool_choice`(`any`, `tool`)는 400이다. thinking을 끄려면 `{"type": "between_tools"}`(effort `high` 이하에서만)를 쓴다. thinking 내용은 기본이 `omitted`라 로그에 남지 않는다. 결정 로그에 추론 요약을 남길지는 `docs/loop.md`에서 정한다(`display: "summarized"`, 비용은 같다)
- [ ] `max_tokens`는 비스트리밍 16000 안팎에서 시작한다. 글 작성 턴이 길어지면 스트리밍으로 바꾼다(큰 `max_tokens`는 SDK 타임아웃에 걸린다)
- [ ] 대화 기록은 덧붙이기만 한다. 응답 `content`를 thinking 블록까지 그대로 돌려보내고, 사이클 중에 system 프롬프트, 툴 목록, 앞 메시지를 바꾸거나 자르지 않는다. 앞부분이 바뀌면 thinking 블록이 무효가 되고, 2026-08-31 이후 만든 계정에서는 400이 난다. 길어질 결과는 툴이 처음부터 짧게 돌려준다
- [ ] 프롬프트 캐시: system(prompt.md)과 툴 정의 끝에 캐시 지점을 둔다. 날짜와 사이클 ID는 지금처럼 첫 user 메시지에 둔다(system에 넣으면 매번 캐시가 깨진다). 두 번째 요청부터 `cache_read_input_tokens`가 0보다 큰지 테스트로 확인한다
- [ ] 툴 호출 60회 상한은 그대로 두고, 요청 수 상한을 따로 둔다

**멈추는 조건** (`stop_reason`)

- [ ] `tool_use`: 툴을 실행하고 결과를 모두 다음 user 메시지 하나에 `tool_result`로 돌려준다. 실패한 툴은 `is_error: true`로 돌려준다
- [ ] `end_turn`: 사이클 끝
- [ ] `max_tokens`: 그 턴의 툴은 실행하지 않는다(입력이 잘렸을 수 있다). `max_tokens`를 올려 한 번 다시 하고, 또 그러면 실패로 끝낸다
- [ ] `refusal`: 툴을 실행하지 않고 멈춘다. `stop_details`의 분류를 기록하고 #긴급으로 알린다. 추천은 서버 쪽 대체(`betas: ["server-side-fallback-2026-07-01"]` + `fallbacks: "default"`)를 켜는 것이다. Claude API에서만 되고 Sonnet 5.5는 `"default"` 형식만 받는다. 보안(gitleaks, 포트)이나 LLM 주제 글에서 안전 분류기가 문제없는 요청을 거절할 수 있다. 켜면 대체로 처리된 요청의 모델과 단가를 따로 기록한다
- [ ] 그 밖(`pause_turn` 등): 서버 툴을 쓰지 않으므로 오류로 본다

**비용과 예산**

- [ ] 요청마다 `usage`(입력, 출력, 캐시 쓰기, 캐시 읽기 토큰)를 `logs/`에 남기고 단가표로 달러를 계산한다. 단가는 `config.py`에 두고 가격이 바뀌면 고친다. Sonnet 5.5는 100만 토큰당 입력 $2, 출력 $10, 캐시 쓰기 $2.50(5분)·$4(1시간), 캐시 읽기 $0.20
- [ ] 비용 비교 기준(2026-10-13 실측): 지금 C3 사이클 5회는 비용의 34~65%가 캐시 쓰기였고, 기록이 캐시 쓰기를 1시간 단가($4/M)로 계산한 값과 정확히 맞는다. C2는 5분 캐시($2.50/M)와 더 작은 접두부(Claude Code 시스템 프롬프트 없음)로 같은 일을 더 싸게 할 여지가 있다. C2 시험에서 같은 상태로 C3와 비교해 확인한다
- [ ] 요청 전에 사이클·하루·월 누적을 보고, 상한("먼저 정할 것" 3번)을 넘으면 요청하지 않고 멈춘 뒤 #긴급으로 알린다
- [ ] 예산 상한은 설정 파일에만 있고, Huninn의 툴로는 바꿀 수 없다
- [ ] Console 한도에 걸렸을 때 루프가 다시 시도하지 않고 #긴급으로 알리는지 확인한다 (claude-billing.md에는 400 오류로 멈춘다고 적혀 있다)

**실패 처리**

- [ ] 429·5xx·529: SDK 재시도(기본 2회) 뒤에도 실패하면 사이클을 실패로 끝내고, 1시간 뒤 한 번만 다시 돈다. 그것도 실패하면 그날은 쉬고 #긴급. 다시 돌아 성공하면 장애 자동 복구로 센다
- [ ] 인증·권한·결제·한도 오류: 다시 돌지 않고 #긴급(critical)
- [ ] `cycle.py`에서 그대로 가져온다: 한 번에 하나(`.cycle.lock` 잠금), 25분 제한, `cycles.jsonl` 기록과 실패 알림, `BLOGOPS_NO_PUBLISH` 시험 실행, `--show`

**프롬프트와 전환**

- [ ] `ops/huninn/prompt.md`: Phase 1 문장(모든 글을 승인받는다, 실험이 없다)을 고치고, 하루 순서에 지표 확인, 실험 결과 확인과 예약, 발행 뒤 공유 대기열을 더한다 (architecture.md 일간 루프 2·4·8단계)
- [ ] 테스트: 가짜 API 응답으로 `stop_reason` 분기, 예산 초과, 재시도, 기록 형식
- [ ] 작업실에서 사이트 사본으로 시험 실행 → 같은 상태에서 C3와 툴 호출 수, 비용, 결과를 비교 → 매장 타이머를 C2로 바꾼다. C3 경로는 한동안 남겨 되돌릴 수 있게 한다
- [ ] C2 사이클의 최대 메모리를 재서 `huninn-cycle.service`의 `MemoryMax`(지금 1G)를 줄인다. C3 실측 최댓값은 427.6MB(2026-10-12)다

#### 운영 지표, 개입 기록, 백업

architecture.md "관측성과 포트폴리오 지표"의 지표를 실제로 계산한다. 계산은 Pi 코드가 하고 Claude는 부르지 않는다.

- [ ] 사람이 한 일 기록: 소개 페이지 "무인 운영의 기준"대로 사람 개입·사람 변경·정해진 역할(승인)을 구분해 남긴다. `review`에 하위 명령을 더한다(예: `review log <분류> "<이유>"`). 승인·반려는 이미 남고, 결정한 곳(`via`: cli·discord)도 디스코드 브랜치에서 남는다. 사람 커밋(`Hun0305`)은 git log에서 모은다. 사람 변경이라도 장애를 고치려는 것이면 개입으로 센다(장애 알림 뒤 24시간)
- [ ] 장애 기록: 사이클 실패, 발행 실패, 상태 점검 문제, 업타임 모니터 다운을 장애로 열고, 다음 정상 신호에서 닫는다 (자동 복구 여부, 걸린 시간)
- [ ] 업타임: 업타임 모니터의 가용률을 읽어 온다. 읽기 전용 API 키를 쓰면 gitleaks 규칙부터 확인한다
- [ ] 지표 계산 (하루 한 번, 타이머): 연속 무인 운영일(장애 24시간 규칙 포함), 개입 수, 장애 자동 복구율, 품질 첫 통과율, 글당 비용, 업타임 → "먼저 정할 것" 4번 파일로 커밋
- [ ] status.json에 연속 무인 운영일과 오늘 비용 더하기. Pi 상태를 5분마다 쓰는 부분은 Phase 1로 앞당겨 만들었다(위 "사이트" 절, [status.md](status.md)). "오늘 비용"은 기록은 달러로 하고 고정 환율로 원화를 환산한 뒤, 통계 탭에 기준 환율과 날짜를 적는다. 두 필드가 생기면 띠의 "운영 준비 중"이 사라진다
- [ ] 통계 탭: 지표 표 문구는 2026-10-13에 새 정의로 맞췄다(사이트 레포 `f39f02e`). 실제 값을 보여 준다
- [ ] 백업 타이머 (순서 0, 앞당김): `logs/`, `state/drafts/`, `state/approvals/`를 매일 압축해 USB에 둔다 (architecture.md 백업 표). 지금은 이 비공개 기록이 SD카드에만 있고 USB 저장장치도 꽂혀 있지 않다(`lsblk`, 2026-10-13). USB 마운트(sudo)는 ops/에 남기고, 한 번은 실제로 풀어서 복구해 본다
- [ ] 30일 지난 `logs/*.jsonl`은 백업한 뒤 압축한다

#### 디스코드 봇 (승인 버튼)

`feat/discord-approval` 브랜치에서 만들었다(2026-10-13 코드·시험 끝, PR·운영 반영 전). 진행 상황과 남은 운영 작업은 위 "다음에 만들고 싶은 것"의 같은 항목에서 본다. 설계는 [blogops.md](blogops.md) 11절이 기준이고, 아래 요구는 거기에 들어 있다. 열린 질문 "폰에서 승인하기"는 2026-10-13 결정으로 닫혔다.

- 지키는 것: 운영자 디스코드 계정 ID만 누를 수 있고, 버튼의 해시가 초안의 지금 해시와 다르면 거부하고(기록 단계에서도 다시 대조), 반려는 사유 입력창을 거치고, 승인·반려 기록에 경로(`discord`, `cli`)를 남긴다
- 초안과 달라진 것: 초안 파일(ko·en) 첨부 대신 실제 사이트 모양의 미리보기 페이지(토큰 주소)를 링크하고, [접기](반려 + 보류 + 글감 `blocked`) 버튼을 더했다
- [ ] `get_system_health`에 봇 상태를 넣는다 (blogops.md 11절 "남은 것")
- [ ] 봇과 대시보드를 합친 메모리를 잰다 (architecture.md 예산은 둘 합쳐 150~200MB, 봇 `MemoryMax`는 200M)

#### 실험 러너와 공통 로거

설계는 `docs/experiments.md`. 원칙은 [edge-ai-blog-topics.md](edge-ai-blog-topics.md)와 architecture.md("실험은 미리 등록한 템플릿만 실행한다")를 따른다. 대기·재시도·집계는 Pi 코드가 하고, Claude는 예약과 해석만 한다 (claude-billing.md 실험 비용 원칙).

**시스템 준비** (sudo, ops/에 스크립트로 남긴다)

- [x] 메모리 cgroup 켜기 (2026-10-12 완료)
- [ ] SSH, Caddy, 터널의 OOM 우선순위를 낮춘다(`OOMScoreAdjust` 드롭인). 메모리가 모자라면 실험이 먼저 죽게 한다. 2026-10-07 확인: 셋 다 기본값 0
- [ ] Cloudflare HTML 캐시 규칙: Pi가 실험으로 바빠도 블로그가 열리게 한다. 짧은 엣지 TTL(예: 10분)로 시작한다. 발행 때 캐시를 비우는 방식은 API 토큰이 하나 더 필요하다

**러너**

- [ ] 템플릿: `experiments/templates/<id>/`에 실행 스크립트와 정의(파라미터 범위, 최대 시간, `MemoryMax`, 시간대, 결과 CSV 열)를 둔다. Huninn은 템플릿 ID와 범위 안의 값만 고른다
- [ ] 큐에서 하나씩 꺼내 systemd 유닛으로 실행한다 (`MemoryMax`, 시간 제한, `Nice`)
- [ ] 실행 규칙
  - 한 번에 하나만. 비전 촬영과 LLM 실험은 겹치지 않는다
  - LLM 실험은 밤(예: 02:00~06:00)에만, 하루 사이클과 겹치지 않게 돈다
  - VS Code 원격 연결이 있으면 LLM 실험을 미룬다 (CLAUDE.md 규칙). 연결 판정 방법(활성 SSH 연결, `vscode-server` 프로세스, `MemAvailable`)은 `docs/experiments.md`에서 정한다
  - CPU 온도가 상한(예: 80°C)을 넘으면 중단하고 기록한다
- [ ] 공통 로거: 실험 동안 1초마다 온도, 클럭, 스로틀링(`vcgencmd get_throttled`), 메모리를 남긴다. RAM(`/tmp`)에 쓰고 끝나면 결과와 함께 저장한다
- [ ] 결과: `experiments/results/<템플릿>/`에 CSV와 측정 조건(모델 파일 해시, 런타임 버전, 커널, 시작 온도)을 둔다. 요약 통계(평균, 중앙값, p99)는 러너가 계산한다. 운영 레포에 커밋한다(공개)
- [ ] 측정 방법(프롬프트 세트, 테스트셋, 지표)은 템플릿마다 문서로 고정한다. 바꾸면 새 버전으로 만들어 회차끼리 비교되게 한다

**blogops**

- [ ] `list_experiments`, `schedule_experiment`(템플릿 ID, 파라미터, 반복 주기), `get_experiment_result`(상태, CSV 경로, 요약 통계). 예약은 하루 상한을 둔다. Huninn은 실험이 끝나기를 기다리지 않고 다음 사이클에 결과를 읽는다
- [ ] 품질 검사 확장 (architecture.md "사실 오류" 가드레일): 실험 시리즈 글은 실험 ID가 있어야 하고, 본문의 측정값(단위가 붙은 숫자)이 그 실험의 요약 통계와 맞아야 하며(반올림 허용), 원본 CSV 링크와 측정 조건이 있어야 한다
- [ ] 시리즈 열기: `config.py`의 `CURRENT_SERIES`(지금 `ops-log`, `weekly-report`)에 `pi-llm`(비전이 준비되면 `pi-vision`)을 더하고, `state/strategy.md`의 Phase 2 절을 고친다

**첫 실험: 소형 LLM** (백로그 `llm-first-run`)

- [ ] 런타임: llama.cpp(`llama-bench`, 빌드 커밋 고정)를 추천한다. 버전을 고정할 수 있고 상주 데몬이 없어 실험 유닛의 `MemoryMax` 안에서 시작하고 끝난다. Ollama는 감 잡기용으로만 쓴다
- [ ] 1B급 4비트 모델 하나로 tokens/s, TTFT, 최대 메모리를 잰다. 프롬프트 세트를 고정한다
- [ ] 첫 글: 측정 조건 표, 원본 CSV 링크, "참고용 벤치마크" 고지, 직접 만든 그래프

**두 번째 실험: 비전** (백로그 `vision-room`)

- [ ] 카메라 연결 확인(`rpicam-still`). 2026-10-13 확인: 지금 Pi에서 카메라가 인식되지 않는다(`/sys/class/video4linux`에 코덱·ISP 장치뿐이고 CSI·USB 카메라가 없다). 장비를 준비하는 것부터 시작한다
- [ ] 낮 시간 10~15분 간격 촬영, 고정 물체 정답 라벨(운영자가 한 번)
- [ ] recall, confidence, 평균 밝기를 잰다. `person`이 잡힌 프레임은 공개하지 않는다 (edge-ai-blog-topics.md "주의")
- [ ] 이미지 해상도와 보관 위치를 정해 SD 쓰기를 줄인다. 오래 쌓을 거면 외장 SSD에 둔다

#### blogops 툴 확장

architecture.md 툴 21개 중 Phase 1에서 만들지 않은 것이다 (blogops.md 2절). 실험 툴 3개는 위 "실험 러너와 공통 로거"에 있고, `unpublish_post`는 사람만 쓴다.

| 툴 | 할 일 | 메모 |
| --- | --- | --- |
| `get_system_health` | 터널 연결, 디스코드 봇, API 키 만료까지 남은 일수, 이번 달 비용과 한도, 도메인 만료(2027-10-06)까지 남은 일수, 지난 실패를 더한다 | API 잔액을 조회하는 공식 방법은 확인하지 못했다. 없으면 이번 달 비용 대 한도로 대신한다. Pi에 Admin API 키는 두지 않는다(조직 관리 권한이라 유출되면 피해가 크다) |
| `get_site_stats` | 기간 → 조회수, 상위 글, 유입 경로 | Cloudflare Web Analytics(쿠키 없는 JS 비컨)를 추천한다. 서버 요청 통계보다 사람 방문에 가깝고, 존 HTTP 통계에는 허용해 둔 AI 크롤러가 섞인다. 읽기 전용 API 토큰을 쓴다 |
| `get_search_stats` | 기간 → 검색 노출, 클릭, 검색어 | Google Search Console API(서비스 계정을 속성에 읽기 사용자로 추가). 네이버는 API가 있는지 확인한다 |
| `get_trends` | 허용 목록의 RSS·API에서 글감 후보와 출처 | GeekNews, HN, 소형 모델 출시 소식(LLM 시리즈의 "신모델" 신호). 제목과 링크만 돌려준다. 외부 텍스트는 데이터로만 다룬다 |
| `update_strategy` | 변경 내용, 근거 → 새 버전 | 범위는 "먼저 정할 것" 8번. 변경 이력 행을 자동으로 더하고, 운영 레포에 Huninn으로 커밋하고, #일일요약에 알린다 |
| `queue_naver_digest` | 발행한 글 → 네이버·커뮤니티·링크드인(영어)용 요약과 공유 문구 | 공유 대기열에 넣기만 한다. 게시는 사람이 한다 |
| `get_week_summary` | 실제 비용, 방문·검색 통계, 실험, 개입과 장애, 게이트 3 진행을 더한다 | 주간 보고서 재료 |

- [ ] 툴마다 테스트를 쓰고, MCP 툴 목록과 C2 루프 양쪽에서 보이는지 확인한다
- [ ] 새 비밀값(Cloudflare API 토큰, Google 서비스 계정 키 등)을 더할 때마다 CLAUDE.md 규칙대로 `ops/gitleaks.toml` 규칙과 `ops/test-pre-commit.sh` 경우를 더한다
- [ ] 툴이 늘었으니 사이클당 툴 호출 상한(60회)을 다시 본다

#### 대시보드 (비공개)

- [ ] FastAPI와 정적 HTML, systemd 서비스. 접근과 역할은 "먼저 정할 것" 7번
- [ ] 화면: 운영 지표와 게이트 3 진행, 사이클 이력(비용, 툴 호출, 실패), 예산 대비 사용량, 승인 대기 초안(읽기), 공유 대기열(처리 표시), 알림 이력, 실험 큐와 결과
- [ ] 대시보드와 봇을 합친 메모리를 잰다 (architecture.md 예산 150~200MB)

#### 주간·월간 루프

- [ ] 주간(일요일): 넓힌 `get_week_summary`로 보고서를 쓰고, `update_strategy`로 전략을 고친다. 예산은 보고서에서 점검만 하고 한도는 사람이 바꾼다. Huninn이 자기 예산 상한을 올릴 수 없게 하기 위해서다
- [ ] 월간(매월 첫 주, 첫 실험 글이 나온 다음 달부터): 기준 실험을 다시 예약 → 시계열 CSV에 더함 → 기존 실험 글을 갱신하고 글 끝에 변경 이력을 남긴다
  - 발행된 글을 고치는 경로가 지금은 없다(`publish_post`는 새 글만 낸다). 승인 모드 동안은 고친 글도 승인을 받는다

#### 사이트

- [ ] 실험 글 형식: 측정 조건 표, 원본 CSV 링크, "참고용 벤치마크" 고지, 그래프. site/README.md 글 형식에 더한다. 그래프는 직접 만든 측정 그래프만 쓴다 (architecture.md 저작권 가드레일)
- [ ] 상태 띠와 통계 탭이 status.json과 가공 지표를 실제로 읽는지 확인한다
- [ ] 방문 통계 비컨을 붙이면 소개 페이지에 밝힌다
- [ ] 첫 글과 소개 페이지의 실행 방식·요금 설명을 API 전환에 맞게 고친다 (수정일 표시)
- [ ] "먼저 정할 것" 9번(측정 창 재계수)을 채택하면 소개 페이지 "승인 모드와 성공 기준"과 첫 글(한·영)에 한 줄 더한다

#### 문서

- [ ] 새 설계 문서 `docs/loop.md`, `docs/experiments.md`를 CLAUDE.md 문서 목록에 더한다
- [ ] architecture.md: 툴 표(blogops.md 2절에서 미뤄 둔 Phase 1 새 툴 6개 포함), 디렉터리 구조(`metrics/`, `experiments/` 아래), 대시보드와 봇(승인 처리 위치 포함)
- [ ] CLAUDE.md 커밋 규칙: Huninn이 운영 레포에 하는 커밋(전략, 백로그, 지표, 실험 결과)의 type을 정한다. 실험 결과는 기존 `exp`를 쓴다
- [ ] claude-billing.md: 실제로 정한 한도와 키 만료일. Console 절차 5번의 `.env`를 `~/.config/huninn/huninn.env`로 고친다(작업실 `.env`는 2026-10-12에 지웠다)
- [ ] ops/README.md: 새 서비스와 타이머(봇, 대시보드, status.json, 지표, 백업, 실험), sudo로 바꾼 설정(OOM, USB 마운트)

### 게이트 3: 승인 모드 해제

**지금 기준** (제안값, 2026-10-12 소개 페이지와 첫 글에 공개): 14일 연속 사람 개입(반려 포함) 0회, 그 14일 동안 처음 품질 검사를 받은 초안 5개 이상, 그중 80% 이상이 첫 검사 통과.

판정하기 전에 필요한 것:

- [x] "사람 개입" 정의와 최소 표본 조건(초안 5개 이상): 위 공개 기준에 들어갔다
- [ ] 개입 기록과 지표 계산이 최근 14일의 개입 수와 품질 첫 통과율을 내 준다 ("운영 지표, 개입 기록, 백업")
- [ ] 측정 창을 다시 세는 조건 ("먼저 정할 것" 9번)

승인 모드를 끄는 코드는 Phase 2 안에 미리 만들어 시험한다. 실제로 끄는 것은 운영자가 게이트 3 통과를 확인한 뒤이고, 그때부터 Phase 3다.

- 승인 모드 해제 기준(2주 무개입, 첫 통과율 80%)은 제안값이다. 운영하면서 조정한다.
- 가공 운영 지표의 형식과 위치: 원본 로그에서 식별자를 뺀 지표를 공개하기로 했다. 어느 폴더에 어떤 형식(JSONL, CSV)으로 매일 커밋할지는 Phase 2에서 로깅을 만들 때 정한다.
- ~~폰에서 승인하기~~ 결정 (2026-10-13): Phase 2를 기다리지 않고 Phase 1 중에 만든다. 미리보기 링크 + #승인 버튼 + 상주 봇. "다음에 만들고 싶은 것"의 같은 항목에서 진행 상황을 본다.
- [ ] 설정 하나(`approval_mode`)로 바뀐다. 끄면 `publish_post`가 승인 대신 품질 통과 해시만 확인하고, 품질을 통과한 초안을 같은 사이클에 발행할 수 있다. 하루 1편과 나머지 검사는 그대로다
- [ ] 끈 상태에서는 #승인 요청 대신 발행 뒤 #일일요약으로 사후 알림을 보낸다
- [ ] 시험 실행(`BLOGOPS_NO_PUBLISH`)으로 끈 상태의 흐름을 확인한다
- [ ] 발행한 글을 사람이 내리는 절차를 ops/README.md에 적는다 (`unpublish_post`는 사람만 한다)
