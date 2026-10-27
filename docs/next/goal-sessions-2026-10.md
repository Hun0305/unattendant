# 자율 작업 세션 2회 보고 (2026-10-22, 2026-10-27)

토큰을 쓰려고 Claude에게 알아서 일하게 둔 세션 두 개의 기록이다. 세션 원본(`~/.claude/projects/-home-hun-unattendant/*.jsonl`)과 git 상태를 대조해서 2026-10-28에 정리했다.

| | 세션 1 | 세션 2 |
|---|---|---|
| 세션 ID | `cfcbbfff` | `1b2ade10` |
| 시각 (KST) | 10-22 04:43 ~ 05:39 | 10-27 19:09 ~ 22:23 |
| 지시 | "해야되는거 다 해봐. 코드 리팩터링이나 문서정리나 추가로 작업할 기능들이나." (Opus 5.5, effort max. `/goal` 명령은 기록에 없음) | `/goal` "블로그에 무엇을 더하고 고치면 좋을지 생각해서 계속 작업해. 5시간 한도에 걸리면 멈춰" → 중간에 `/goal`로 "한도까지 계속" 재지정 |
| 끝난 이유 | 사용 한도 직전에 스스로 정리하고 멈춤 | 세션 한도 도달 (22:23, 작업 도중에 끊김) |
| 결과물 | **로컬 커밋 7개** (push 안 함) | **커밋 없음.** 워크트리 3개에 미커밋 변경 |

> **가장 먼저 볼 것:** 세션 2는 세션 1이 이미 커밋한 `get_draft`와 엔진 모래상자(`BLOGOPS_NO_NOTIFY`, `--item`, `sandbox.sh`)를 모른 채 다시 만들었다. 합치기 전에 어느 쪽을 쓸지 정해야 한다. 자세한 내용은 [3절](#3-두-세션이-겹친-곳)에 있다.

---

## 1. 세션 1: 2026-10-22 새벽 (커밋 7개)

먼저 todo, 문서, 코드 전체와 매장 로그, 타이머 상태를 읽어 할 일을 골랐다. 시작 시점에 테스트는 agent 184개와 실험 러너 25개가 모두 통과했다.

### 1.1 `feat/auto-english` (작업실 `~/unattendant`, origin보다 3개 앞섬)

| 커밋 | 내용 |
|---|---|
| `03c82b0` docs | 이전 세션이 쓴 엔진 선택 설계(`docs/engines.md`)와 관련 문서 커밋 |
| `099f5f3` ops | 밤 실험 타이머를 재부팅 뒤에도 남는 **사용자 유닛**으로 바꾸고 설치. 그때까지 실험이 한 번도 돌지 않았던 이유는 두 가지였다. 매일 밤 VS Code 서버가 떠 있었고, 10-19 재부팅 때 임시 타이머가 사라졌다. 첫 실행은 10-23 02:00으로 잡았다 |
| `990c08f` docs | todo.md와 ops/README.md를 실제 운영 상태에 맞춤. 봇, 반려 직후 실행, 상태 파일, 미리보기는 이미 운영 중이었다. 게이트 2는 4/5, 메모리 cgroup은 켜져 있다. 상태 띠는 헤드리스 Chromium 스크린샷으로 확인했다 |

### 1.2 기능 브랜치 4개 (worktree `~/unattendant-claude`)

| 브랜치 / 커밋 | 내용 | 테스트 |
|---|---|---|
| `fix/get-draft` `403fdc2` | 초안 본문을 읽는 MCP 툴 `get_draft` 추가, 프롬프트 3번 수정. 10-16 사이클이 반려된 초안의 본문을 못 읽고 제목만 고친 문제를 고친다 | 186 통과, 실제 대기 초안으로 읽기 확인 |
| `fix/cycle-alerts` `1b1ba78` | 사이클 실패 알림에 원인 분류(인증, 한도 등), "연속 N번째: 언제부터", 토큰 재발급 방법을 붙임 | 188 통과 |
| `feat/engine-select` `451127d` (cycle-alerts 위) | 엔진 선택 구조(Claude 경로만 구현, agy 경로는 만들지 않음), 초안 기록에 엔진과 모델 남김, `BLOGOPS_NO_NOTIFY`, 엔진 비교용 모래상자 `ops/huninn/sandbox.sh` | 196 통과, 가짜 claude로 끝까지 시험 |
| `refactor/site-helpers` `4278f0f` | git과 Hugo 중복 코드를 `gitrepo.py`·`hugo.py`로 모음. `frontmatter.parse_loose` 추가. 동작은 같다 | 185 통과, 실제 사이트 빌드 확인 |

### 1.3 남긴 것

- `fix/get-draft`와 `feat/engine-select`는 4개 파일에서 충돌한다(README, blogops.md, 테스트 2개). 한 줄로 쌓는 rebase를 하던 중에 한도가 와서 rebase를 취소하고 멈췄다.
- 합치는 순서: `feat/auto-english`를 먼저 main에 합쳐야 한다. 나머지 브랜치가 모두 그 위에 있다.
- 같은 시간에 다른 세션(agy)이 진단 보고서를 쓰고 CLAUDE.md를 고치고 있어서, 그 파일들은 건드리지 않았다.

---

## 2. 세션 2: 2026-10-27 저녁 (미커밋, 워크트리 3개)

진행 흐름은 이렇다.

1. 첫 `/goal`을 받고 Gemini 보고서(`docs/gemini-consulting.md`) 항목 중 실제로 맞는 것부터 고쳤다.
2. 중간에 **Gmail 4통**(Search Console 색인 3통, Cloudflare 1통)을 이 Pi에서 직접 확인해 달라는 요청을 처리했다.
3. 두 번째 `/goal` 뒤로 컨텍스트 압축이 2번 있었다. 중간 보고로 끝내려 할 때마다 Stop 훅이 2번 되돌려 보냈다.
4. 22:23에 엔진 모래상자를 만들던 중 세션 한도로 끊겼다.

### 2.1 Gmail 확인 결과

| 메일 | 원인 | 조치 |
|---|---|---|
| Search Console Soft 404 (10-26, 2통) | 사이트맵에 글이 0편인 시리즈 페이지 6개(`pi-llm`, `pi-vision`, `weekly-report` × ko/en)가 들어 있고, 본문이 "아직 발행된 글이 없습니다."뿐이다. `/numbers/`도 JS 전 HTML에 오류 문구가 들어 있었다 | 빈 term에 noindex를 달고 사이트맵에서 뺌. `/numbers/` 기본 문구를 "불러오는 중"으로 바꿈 (site 워크트리) |
| robots.txt 차단 (10-25) | 본 사이트는 `Allow: /`. `preview.unattendant.dev`만 `Disallow: /`이고, 이건 의도한 설정이다 | Search Console에서 그 URL이 preview 주소인지 **직접 확인 필요** |
| Cloudflare | 연결이 끊긴 게 아니라 보안 업그레이드 요청이다(cloudflared 2026.10.2 이상 필요). 이 Pi는 .deb로 설치돼서 apt로는 안 올라간다. 원본이 HTTP라 인증서 경고는 해당 없다 | `ops/upgrade-cloudflared.sh` 작성(2026.10.4 .deb, sha256 대조, 터널 재시작). **아직 실행 안 함**, 2026-10-28 현재도 2026.9.1 |

### 2.2 사이트 워크트리 `~/unattendant-wt/site` (사이트 레포, 브랜치 `feat/site-share`)

수정 29개 파일(+529/−85)과 새 파일 다수가 있다.

- **검색·공유**
  - 언어별 링크 미리보기 기본 카드(`scripts/og-card.py`, IBM Plex로 그림)와 글마다 제목이 든 카드(`cover.{ko,en}.png`). 발행된 5편의 카드 10장도 만들어 둠
  - hreflang `x-default`가 모든 글에서 홈을 가리키던 문제 수정
  - 구조화 데이터 JSON-LD(BlogPosting)
  - `/llms.txt`
  - `/posts/`의 `<title>`이 "posts"로 나오던 문제 수정
- **RSS**
  - 전문 피드(`content:encoded`)로 바꾸고, 소제목 `#`는 빼고 링크는 절대 주소로 바꿈
  - 요약은 front matter의 `description` 사용
  - 시리즈·태그별 피드에도 같은 템플릿을 쓰고, 시리즈 페이지에 구독 링크를 둠
  - 푸터에 RSS와 GitHub 링크 추가
- **글 페이지**
  - 읽는 시간
  - 목차(소제목 4개 이상일 때)와 소제목 링크
  - 코드 하이라이트를 DESIGN.md 토큰 색으로 바꿈
  - 발행 기록(receipt) 블록과 GitHub 변경 이력 링크
  - 그림 출처 목록(`fig`의 `by` 값)
  - 영어판에서 한국어 원문으로 가는 링크
- **상태 띠**
  - Huninn이 실패 중이면 "Huninn 멈춤 · 10월 17일부터 N회 연속 실패"를 띄움
  - 통계 탭에 "Huninn 마지막 실행" 줄과 띠 읽는 법 추가
  - 인라인 스크립트를 `assets/js/status.js`로 빼서 CSP를 걸 수 있게 함
- **기타**
  - 파비콘, 주소창 색
  - 404 페이지에 최근 글
  - 홈에서 빈 시리즈는 "준비 중"으로 표시
  - 인쇄용 스타일
  - 배포 전 검사 스크립트 `scripts/check.py`: 지금 브랜치는 통과(페이지 81개, 문제 0개)하고, 라이브 판에서는 인라인 스크립트 50건을 잡는다
- **승인이 필요한 공개 글 수정**
  - `pi-blog-no-open-ports`의 MemoryMax 정정문
  - 소개 페이지의 사실 세 곳(타이머 시작일, 툴 개수, 하루 순서)

### 2.3 운영 워크트리 `~/unattendant-wt/get-draft` (운영 레포, 브랜치 `feat/blogops-improvements`)

수정 32개 파일(+886/−82)과 새 파일 `tests/test_health.py`, `ops/huninn/sandbox.sh`가 있다. **2026-10-28 다시 돌려 본 결과 테스트 209개가 통과한다.**

- `get_draft` 툴 (세션 1과 겹침)
- `get_strategy`가 다른 초안들의 과거 반려 사유도 함께 돌려줌. 프롬프트가 새 초안을 쓰기 전에 이걸 읽게 함
- 초안 고칠 때마다 `history/`에 스냅샷을 남김. `review diff <id>` 명령, 승인 메시지에 "반려 뒤 바뀐 것: 제목, 본문은 그대로" 한 줄
- 발행할 때 front matter에 `receipt`(사이클, 모델, 품질 검사 횟수, 반려 횟수, Pi 온도·메모리)를 기록. 초안 meta에 모델 기록
- 기존 AI 글 4편의 receipt를 로그로 다시 만드는 `review receipts`(출력만, 파일은 안 고침)
- `review status`: SSH로 들어와 마지막 사이클, 상태 점검, 처리할 초안을 한 번에 봄
- `status.json`에 `cycle` 필드(마지막 실행, 연속 실패 횟수, 실패 시작 시각)
- 상태 점검(`get_system_health`)에 notices 추가: 봇 멈춤, 상태 파일 오래됨, 지난 사이클 실패
- 품질 검사
  - 내부 글 링크가 실제로 있는지 확인
  - 그림 `by` 누락 검사
  - 영어판과 한국어판의 `by` 불일치 검사
- 발행·영어판 붙이기 때 글 카드(`cover.*.png`)를 만들어 같은 커밋에 넣음. 실패해도 발행은 그대로 감
- front matter 파서가 여러 줄 YAML 목록을 읽음
- 엔진 모래상자: `BLOGOPS_NO_NOTIFY`, `--item`, `sandbox.sh` (세션 1과 겹침, 끊기기 직전 작업이라 마무리 안 됨)
- 문서 반영: `docs/blogops.md`, `docs/status.md`, `docs/todo.md`, `ops/huninn/prompt.md`, `agent/README.md`, `CLAUDE.md`(툴 21개)

### 2.4 ops 워크트리 `~/unattendant-wt/caddy` (운영 레포, 브랜치 `feat/ops-hardening`)

- Caddyfile에 보안 헤더(nosniff, Referrer-Policy, X-Frame-Options, Permissions-Policy)와 CSP 추가. 폰트와 `/js/*`는 1년 캐시. 임시 Caddy(:18080)에서 CSP 위반 0건을 확인함
- Caddy, 터널, ssh에 `OOMScoreAdjust=-500`을 걸고 설치 스크립트 `ops/install-oom-guard.sh`(sudo) 작성
- `ops/upgrade-cloudflared.sh` 사본, ops/README와 todo 반영
- **배포 순서:** 사이트(외부 JS 판)를 먼저 배포하고, 그다음 Caddy를 재시작해야 한다. 순서가 바뀌면 상태 띠가 "운영 준비 중"에 머문다

### 2.5 세션 끝 상태

- 마지막에 `/goal celar`(clear 오타)를 입력해서 "celar"라는 목표가 걸린 채로 끝났다. 이 세션을 `--resume`으로 다시 열면 그 목표를 향해 일하려 할 수 있으니, 열자마자 `/goal clear`를 입력할 것.
- 같은 사본이 작업실 `~/unattendant`에도 미추적 파일 `ops/upgrade-cloudflared.sh`로 남아 있다.

---

## 3. 두 세션이 겹친 곳

| 기능 | 세션 1 (커밋됨) | 세션 2 (미커밋) |
|---|---|---|
| `get_draft` 툴 | `fix/get-draft` `403fdc2` | `feat/blogops-improvements`. 반환값이 더 많다(last_rejection, last_quality 등) |
| 모래상자 (`BLOGOPS_NO_NOTIFY`, `--item`, `sandbox.sh`) | `feat/engine-select` `451127d`, 끝까지 시험함 | 같은 이름으로 다시 만듦. 끊기기 직전이라 미완성 |
| `cycle.py` | `fix/cycle-alerts`가 실패 알림을 고침 | 모델 전달, `--item` 추가 |

권장 순서는 이렇다.

1. 세션 2의 `get_draft`가 기능이 더 많으니 그쪽을 쓰고 `fix/get-draft`는 버린다.
2. 모래상자는 세션 1의 `feat/engine-select`(시험 완료)를 기준으로 삼는다.
3. 세션 2 워크트리의 모래상자 조각은 빼거나, engine-select를 합친 뒤 그 위로 rebase하며 정리한다.
4. 둘 다 `cycle.py`를 고쳐서 충돌이 예상된다.

---

## 4. 아직 사람이 해야 하는 일

| 우선 | 일 | 상태 (2026-10-28 확인) |
|---|---|---|
| 1 | Claude 토큰 재발급(`claude setup-token` → `~/.config/huninn/huninn.env`) | Huninn이 10-17부터 매일 실패. 10-27 14:00까지 11회 연속 |
| 2 | `sudo bash ops/upgrade-cloudflared.sh` 후 ops/README 버전 표 고치기 | 아직 2026.9.1 |
| 3 | Search Console에서 robots 차단 URL이 preview 주소인지 확인 | 미확인 |
| 4 | 브랜치 정리와 합치기: `feat/auto-english` → main, 그다음 3절 순서대로. 세션 2 워크트리는 기능 단위로 나눠 커밋 | 커밋·push 요청 대기 |
| 5 | 머지 뒤 매장 pull, 사이트 배포, `sudo bash ops/install-oom-guard.sh`(Caddy 재시작에 CSP도 같이 적용) | 대기 |

### 운영자가 결정할 것

- 공개 글 수정 승인
  - `pi-blog-no-open-ports` 정정문
  - 소개 페이지 사실 수정
  - 기존 글 5편에 카드와 그림 `by` 추가
- 상태 띠에 Huninn 실패를 공개할지
- `review receipts` 결과를 기존 AI 글 4편 front matter에 넣을지
- 보류한 제안
  - `read_record` 허용 범위 확대(지금은 테스트로 일부러 막아 둔 설계)
  - 상투어·콜론 제목 차단(prompt.md 원칙 7과 부딪침)
  - 실험 결과(LLM 리더보드)를 통계 탭에 공개할지
- 쓰지 않는 worktree 정리: `~/unattendant-claude`, `~/unattendant-worktree-practice`

---

## 5. 2026-10-28 정리 결과

세션 2의 미커밋 변경을 기능 단위로 나눠 커밋했다. 모두 로컬 커밋이고 push는 하지 않았다. 커밋마다 index 내용을 꺼내 테스트(운영)나 Hugo 빌드(사이트)를 돌려 통과한 것만 남겼다.

| 워크트리 | 브랜치 (기준) | 커밋 | 확인 |
|---|---|---|---|
| `~/unattendant-wt/get-draft` (운영 레포) | `feat/blogops-improvements` (990c08f) | 12개 (fix 3, feat 9) | 커밋마다 agent 테스트, 마지막 207개 통과 |
| `~/unattendant-wt/caddy` (운영 레포) | `feat/ops-hardening` (990c08f) | 3개 (OOM, Caddy 헤더·CSP, cloudflared 스크립트) | `caddy validate`, `bash -n`, cloudflared sha256을 GitHub 릴리스와 대조 |
| `~/unattendant-wt/site` (사이트 레포) | `feat/site-share` (4ed4a45) | 25개 (기능 20, 공개 글 변경 `content(human)` 5) | 커밋마다 Hugo 빌드 경고 0, 마지막에 `scripts/check.py` 통과 |

- **겹친 기능**: `get_draft`는 세션 2 것을 커밋했다(`fix/get-draft` 403fdc2는 버릴 후보). 모래상자 조각(`BLOGOPS_NO_NOTIFY`, `--item`, `sandbox.sh`)은 커밋에서 빼고 `feat/blogops-improvements` 워크트리의 `git stash`("세션2(10-27) 모래상자 조각")에 보관했다. 모래상자는 세션 1의 `feat/engine-select`를 쓴다.
- **공개 글 변경은 따로 뺄 수 있게 커밋했다**: 통계 탭 띠 설명, 포트 글 정정, 소개 페이지, 그림 `by`, 기존 5편 카드. 상태 띠의 Huninn 실패 표시(`feat(site)`)도 따로 있다. push 전에 원하지 않는 것은 빼면 된다.
- **비밀값 노출**: 세션 2 기록(`~/.claude/projects/-home-hun-unattendant/1b2ade10….jsonl`)에 디스코드 봇 토큰 값이 그대로 남아 있다. 시험이 실패하며 출력한 것이다. git 이력과 레포 파일에는 없다(2026-10-28 확인). 재발은 `fix(agent)` 커밋(시험이 매장 비밀값을 읽지 않게)으로 막았다. 토큰 재발급은 운영자가 정한다.
- **남은 합치기 순서**: `feat/auto-english` → main. 그다음 운영 레포의 `feat/blogops-improvements`, `feat/ops-hardening`, `fix/cycle-alerts`, `feat/engine-select`(`cycle.py` 충돌 예상), `refactor/site-helpers`. 사이트는 `feat/site-share`를 먼저 배포한 뒤 Caddy CSP를 적용한다.
