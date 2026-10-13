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
- [ ] 외부 업타임 모니터(UptimeRobot 등) → 디스코드 #긴급 웹훅. 업타임 기록을 첫날부터 쌓는다

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
- [ ] 그림 포함 글의 첫 자동 발행 확인 (2026-10-13 14:00 사이클): `ai-site-first-screens`가 승인된 상태. 그림 2개 복사, 커밋 메시지의 "그림 2개", 공개 URL의 그림 접근, 새 초안의 그림 제안(전략 v3)을 확인한다
- [ ] IndexNow 실제 사용 (뒤로 미룸, 2026-10-07 결정): 키 파일 `site/static/<키>.txt`를 사이트 레포에 커밋·배포한 뒤 첫 소개글로 실제 색인 요청. 그 전까지 `request_indexing`은 키가 없다고 알리고 건너뛴다. 방법은 [indexnow.md](indexnow.md)
- [x] 비용 로그: `claude -p --output-format json`의 `total_cost_usd`를 사이클마다 기록하고 `estimate: true`로 표시 (Phase 2 실제 청구와 섞지 않는다) → 2026-10-07 `cycle.py`가 `logs/cycles.jsonl`에 남긴다(모델별 사용량 포함). `get_week_summary`가 주간 합계를 쓴다

### 사이트

- [x] 글에 그림 넣기 (2026-10-12, 사이트 레포 `3479e2e`·`f2bf6ec`): `fig` 단축 코드(SVG는 본문에 넣어 다크 모드를 따름), 이미지 규칙을 "측정 그래프만"에서 "누가 만들었는지 밝히고, 남의 그림은 퍼블릭 도메인·허락된 것만, 그림당 200KB 이내"로 바꿈(site/README.md). 첫 글 `name-given-to-me`에 신화 삽화(SÁM 66, 퍼블릭 도메인)와 SVG 두 장을 직접 넣었다
- [x] 전략 v3 "시각자료" 절: 글마다 1~3개, 그래프 → 다이어그램 → 사진·도판(출처 표기) → AI 그림(밝히기) 순. 지금 Huninn은 그림을 받거나 만들 수 없어 #일일요약 "그 밖에"에 그림 제안만 적는다
- [ ] Huninn이 쓰는 글에 그림 넣기 (blogops 지원, 2026-10-12 운영자가 만들고 싶다고 함)
  - [x] 최소 지원 (2026-10-12, PR #3 `a351857`): 초안 폴더의 그림(svg·png·jpg·webp·gif)을 승인 해시에 포함, 발행 때 글 폴더로 복사, 품질 검사(`fig`와 파일 일치, `caption` 필수, 래스터는 `alt` 필수, 파일당 200KB, SVG의 `<script>`·외부 참조 금지), `review show`에 그림 표시. 사이트 README의 "이미지는 측정 그래프만" 규칙은 "누가 만들었는지 밝히면 가능"으로 바꿈. 지금은 운영자가 파일을 넣고 본문에 `fig`를 쓴다 (`ai-site-first-screens`가 첫 사례)
  - [ ] Huninn이 직접 그림 자리를 제안하고 SVG를 만들기: 지금 Huninn은 그림을 받거나 만들 수 없다. 초안에 SVG를 함께 올리는 툴(예: `add_figure`)을 만들어 다이어그램은 Huninn이 직접 그리게 한다. 사진·AI 그림은 계속 제안만(운영자가 준비) 또는 이미지 생성 도구를 붙일지 따로 정한다
  - [ ] AI가 만든 그림 표시를 구조화: 지금은 캡션 문장으로만 밝힌다. front matter나 `fig`의 `by`(human·ai·pd) 속성으로 받아 글 하단에 "그림 출처" 목록을 자동으로 만들고, 품질 검사에서 `by` 누락을 잡는다
  - [ ] 그림 제안 방식 점검: 전략 v3대로 Huninn이 #일일요약에 그림 제안을 쓰는지 확인 (첫 확인은 2026-10-13 사이클)

- [x] 상태 띠 링크 문구 "라즈베리파이 한 대에서 돌아갑니다 →" 고치기 (`site/i18n/ko.toml`의 `bandLink`, 영어판 `en.toml` "Running on a single Raspberry Pi"도 함께) → 2026-10-12 고치지 않고 링크째 삭제(통계 탭 메뉴와 겹침). 같은 날 메뉴 "숫자" 탭 이름을 "통계"로 바꿈(주소 `/numbers/`는 유지)
- [x] 블로그 페이지 디자인 다듬기: 사람이 읽고 싶은 화면으로. 홈 글 목록, 글 본문(글꼴, 글 폭, 줄 간격, 제목 위계, 표·코드·그림), 모바일, 다크 모드를 본다. 레이아웃 구조는 E안 그대로 ([layout-options.md](layout-options.md)) → 2026-10-12 데이터시트형(IBM Plex Sans KR·Mono, 기판 초록 상태 띠, 가로 괘선 표)으로 바꿔 배포. 기준과 결정 경위는 사이트 레포 `DESIGN.md`
- [ ] (친구 피드백, 2026-10-07) 어떤 AI 모델을 쓰고 자동화 파이프라인을 어떻게 짰는지 명시. 지금 첫 글 "두뇌" 부분은 "Claude. 처음에는 Claude Code를 스크립트로…"뿐이다
  - 모델: 정확한 모델 이름과 버전, effort, 인증 방식(Phase 1 Pro 구독 → Phase 2 API). 모델은 실행 스크립트 기본값 `claude-sonnet-5-5`로 정해졌다(`agent/blogops/cycle.py`, 2026-10-07)
  - 파이프라인: systemd 타이머 → `claude -p` → blogops MCP 툴(초안 → 품질 검사 → 승인 요청 → 발행) → Hugo 빌드 → 공개 URL 확인 → 색인 요청. 그림 하나로 보여준다
  - 어디에: 첫 글 "두뇌" 부분 보강(수정일 표시), 소개 페이지, 글마다 쓴 모델을 글 하단에 표시할지 검토
- [ ] (친구 피드백, 2026-10-07) 첫 글 성공 기준 1 "사람 개입 없이 4주 이상 연속 운영"에서 무인 운영의 기준을 정확히 정의
  - 무엇이 "개입"인지: 승인·반려, 초안 수정, 서비스 재시작, 설정·코드 수정, 보안 업데이트(`apt upgrade`), 토큰 갱신 같은 경우를 하나씩 정한다. 설계 문서는 지금 "수동 승인을 제외한 수동 조작·수정"뿐이다
  - 4주를 언제부터 세는지: 승인 모드 해제(게이트 3) 뒤부터인지, 개입이 한 번 생기면 0일부터 다시 세는지
  - 장애가 났지만 자동 복구된 날은 무인 운영일로 치는지
  - 정한 정의를 첫 글(수정일 표시), 숫자 탭(`/numbers/`), architecture.md 지표 표에 같은 문장으로 맞춘다. 개입 로그도 이 정의대로 기록한다

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
- [ ] Huninn이 쓴 글 5편 발행 (1/5, 2026-10-12): 1. "내 이름 Huninn은 어떻게 정해졌나" (`name-given-to-me`). 다음은 승인 대기 중인 `ai-site-first-screens`
- [ ] 품질 게이트 통과율 기록 시작 (지금까지 초안 2개 모두 첫 검사 통과, 반려 1건은 내용이 아니라 주제·제목 문제였음)

## 다음 단계 준비: Phase 2 (API 크레딧으로 바꾸기)

- [ ] Anthropic Console: 크레딧 충전, 조직 월 한도, Huninn 전용 워크스페이스와 월 한도, 서비스 계정, 워크스페이스로 한정한 API 키 (절차는 [claude-billing.md](claude-billing.md))
- [ ] 인증 전환: `.env`의 `CLAUDE_CODE_OAUTH_TOKEN` → `ANTHROPIC_API_KEY`. 구독 토큰은 지우고, `settings.json`의 `forceLoginMethod`를 `console`로 바꾼다
- [ ] Phase 1의 추정 비용과 Phase 2 실측 비용을 비교해 모델(Sonnet 5.5 / Opus 5.5)과 워크스페이스 한도를 정한다

## 열린 질문

- 승인 모드 해제 기준(2주 무개입, 첫 통과율 80%)은 제안값이다. 운영하면서 조정한다.
- 가공 운영 지표의 형식과 위치: 원본 로그에서 식별자를 뺀 지표를 공개하기로 했다. 어느 폴더에 어떤 형식(JSONL, CSV)으로 매일 커밋할지는 Phase 2에서 로깅을 만들 때 정한다.
- ~~폰에서 승인하기~~ 결정 (2026-10-13): Phase 2를 기다리지 않고 Phase 1 중에 만든다. 미리보기 링크 + #승인 버튼 + 상주 봇. "다음에 만들고 싶은 것"의 같은 항목에서 진행 상황을 본다.
