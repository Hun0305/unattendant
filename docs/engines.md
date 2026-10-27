# LLM 엔진 선택: Claude Code와 Antigravity CLI(Gemini)

Oct 22, 2026 · @hun

Huninn의 하루 사이클을 어떤 LLM CLI로 돌릴지 고를 수 있게 하고, Gemini 4 Argon과 Claude Sonnet 5.5가 같은 일을 얼마나 잘하는지 비교하는 설계다. 진행 상황은 [todo.md](todo.md) Phase 1 "엔진 선택과 Gemini 비교"에 체크한다.

**결정 (2026-10-22)**

- `cycle.py`에 엔진 선택(`HUNINN_ENGINE=claude|antigravity`)을 붙인다. 기본값은 `claude`로 두고 비교 결과를 보고 바꾼다.
- Gemini는 **Antigravity CLI(`agy`) + Google AI Pro 구독 로그인**으로 돌린다. Gemini CLI와 유료 API 키는 대안(B안)으로 남긴다 (2절).
- blogops, MCP 서버, 승인·발행·품질 검사는 바꾸지 않는다. 바뀌는 곳은 사이클 실행부(`cycle.py`)와 엔진별 설정 파일뿐이다.

**배경**: 2026-10-17부터 10-21까지 사이클 5회가 연속으로 실패했다. 원인은 `Failed to authenticate: OAuth token revoked`다. 1년짜리 구독 토큰(`claude setup-token`, 2026-10-06 발급)이 만료되기 전에 취소됐다. 실패 알림은 매번 #긴급으로 갔지만(기록에 `notify_error` 없음) 운영자가 놓쳤다. 다시 연결하는 김에 "Gemini가 글을 더 잘 쓴다"는 이야기를 직접 확인해 보기로 했다.

## 1. 바뀌는 것과 바뀌지 않는 것

architecture.md의 핵심 원칙("툴 로직은 `blogops` 하나에 두고 런타임은 갈아끼울 수 있게")이 그대로 적용된다. 엔진을 바꿔도 설계를 바꿀 필요는 없다.

| 그대로 | 바뀜 |
| --- | --- |
| blogops 툴 21개와 서버 쪽 검사(품질, 승인, 발행 한도, 사이클당 툴 호출 60회) | `cycle.py`: 실행 명령, 환경변수, 결과 파싱을 엔진별로 나눈다 |
| MCP 서버(stdio), 시스템 프롬프트 내용(`ops/huninn/prompt.md`) | 엔진별 설정 원본: `ops/huninn/settings.json`(Claude), `ops/huninn/agy-settings.json`(새로 만든다) |
| 매장·작업실 구조, 14:00 타이머, 반려 직후 실행, 동기화 | `logs/cycles.jsonl`에 `engine` 필드, 비용 계산 방식 |
| 모든 글은 사람이 승인한다 (Phase 1) | 프롬프트를 넣는 방식: agy는 시스템 프롬프트를 바꿀 수 없다 (4절) |

Phase 2의 C2(API + 자체 루프)를 어느 모델로 만들지는 이 비교 결과를 보고 정한다. 이 문서는 C3(CLI headless) 단계만 다룬다.

## 2. 조사 결과 (2026-10-22)

가격·쿼터·약관은 바뀔 수 있다. 결정 전에 [출처](#출처)를 다시 확인한다.

### Gemini를 CLI로 부르는 두 길

| | Antigravity CLI (`agy`) | Gemini CLI (`gemini`) |
| --- | --- | --- |
| Google AI Pro 로그인 | 된다. 대화형으로 한 번 로그인하면 `-p`가 그 자격증명을 쓴다 | **안 된다.** 공식 쿼터 문서: "Gemini CLI was replaced by Antigravity CLI on June 18th, 2026" |
| Gemini 4 Argon | 된다 (`agy models`에 `gemini-4-argon-{low,medium,high}`) | 불확실. 같은 문서에 "To use Gemini 4 Argon, please use Antigravity" |
| API 키 | 안 된다 (BYOK 미지원, plans 문서) | 된다 (`GEMINI_API_KEY`, Vertex) |
| 무인 실행 설정 | 일부만 있다 (4절의 ❌ 세 개) | 다 있다: `GEMINI_CLI_HOME`, `GEMINI_SYSTEM_MD`, policy engine(TOML), `tools.core` |
| 소스 | 비공개 | 오픈소스 |

`agy`는 이 Pi에 이미 있다: `~/.local/bin/agy` 1.3.4(바이너리 213MB, aarch64), 사람 계정으로 로그인돼 있다(`~/.gemini/antigravity-cli/`). `agy models`에는 Claude Sonnet 5.5·Opus 5.5도 있다.

### 돈과 한도

| 길 | 비용 | 한도 |
| --- | --- | --- |
| A. `agy` + AI Pro (채택) | 0원 (이미 구독 중) | 5시간마다 회복되는 쿼터 + 주간 한도. 수치는 공개되지 않고 "가용 용량에 따라" 정해진다. 사람이 `agy`를 쓴 만큼 줄어든다. Pro 사용자가 프롬프트 두 번 만에 "Individual quota reached"에 걸렸다는 보고가 있다 |
| B. Gemini CLI + 유료 API 키 | Argon 100만 토큰당 입력 $2·출력 $10, **2026-12-01부터 $4·$20**. 무료 등급에서는 Argon을 쓸 수 없다 | 돈을 내는 만큼 |

- **AI Pro의 개발자 혜택**: 2026-01-27부터 AI Pro 구독자는 Google Developer Program을 통해 **매달 Google Cloud 크레딧 $10**을 받는다(Ultra는 $100). Gemini API(AI Studio, Vertex)에 쓸 수 있다. 자동으로 들어오지 않아 developers.google.com/program/my-benefits에서 활성화하고 GCP 프로젝트를 골라야 한다. 다음 달로 넘어가지 않는다. AI Studio 키 사용량에 그대로 빠지는지와 넘친 만큼 청구되는지는 확인하지 못했다.
- **B안 비용 짐작**: 지난 정상 Claude 사이클 10회의 추정 비용은 회당 $0.02~0.45였다(Sonnet 5.5 단가 $2·$10, Argon 출시가와 같다). 비슷한 토큰을 쓴다면 하루 1회 기준 월 $3~13이고, 12월부터는 두 배다. $10 크레딧으로 비교 실험은 충분하고, 매일 운영은 12월부터 넘칠 수 있다.
- **무료 등급(Flash)은 쓰지 않는다**: 입력이 Google 제품 개선에 쓰인다. 미발행 초안은 비공개다.
- **Antigravity의 추가 사용**: 쿼터를 넘으면 AI credits로 이어 쓰는 설정(`useG1Credits`)이 있다. Claude의 usage credits처럼 Huninn 설정에서는 끈다.

### A안을 고른 이유와 위험

이미 설치·로그인돼 있고, 돈이 들지 않고, Argon을 확실히 쓸 수 있다. 위험은 세 가지다.

1. **쿼터**: 사이클 하나가 툴을 4~22회 부르고 글을 길게 쓴다. 쿼터에 사이클 중간에 걸리면 초안이 반쯤 남는다.
2. **인증 끊김**: 이번 Claude 장애와 같은 종류다. `agy` 자격증명의 수명은 문서에 없다.
3. **가드레일**: Claude Code처럼 기본 도구를 통째로 끄는 옵션과 설정 폴더를 바꾸는 옵션이 없다. 4절의 시험을 통과하기 전에는 blogops를 붙인 실제 사이클을 돌리지 않는다.

쿼터나 인증 때문에 사이클이 자주 끊기면 B안으로 옮긴다. 그때를 위해 $10 크레딧을 미리 활성화해 둔다.

## 3. 엔진 선택 구조 (`cycle.py`)

```
HUNINN_ENGINE=claude       claude -p ... (지금 그대로)
HUNINN_ENGINE=antigravity  HOME=~/.config/huninn/agy agy -p ... --output-format json
run-cycle.sh --engine antigravity --model gemini-4-argon-medium   (한 번만 바꿔 돌릴 때)
```

- **엔진마다 세 가지를 따로 둔다**: 실행 명령(`command`), 넘길 환경변수(`env`), 결과 파싱(`summarize`). 나머지(잠금, 25분 제한, 동기화, 툴 호출 집계, 실패 알림, `--show`)는 공통이다.
- **엔진별 기본 모델**: claude는 `claude-sonnet-5-5`(지금 그대로), antigravity는 `gemini-4-argon-medium`(추천. `high`는 쿼터를 빨리 쓴다). `HUNINN_MODEL`, `--model`로 바꾼다.
- **기록 필드** (`logs/cycles.jsonl`)

| 필드 | claude | antigravity |
| --- | --- | --- |
| `engine` | `claude` | `antigravity` |
| `engine_error` | `is_error` (예전 기록에는 `claude_error`로 남아 있다) | `status`가 `SUCCESS`가 아니거나 `error`가 있을 때 |
| `num_turns` | `num_turns` | `num_turns` |
| 소요 시간 | `duration_api_ms` | `duration_seconds` |
| 토큰 | `modelUsage` | `usage`(input, output, thinking, cache_read, total) |
| `total_cost_usd` | CLI가 계산한 추정치 | 토큰 × Argon API 단가로 계산한 추정치. 단가표는 `config.py`에 두고 12-01 인상을 반영한다 |
| `estimate` | `true` | `true` (구독이라 실제 청구가 아니다) |

- **글에 엔진을 남긴다**: cycle.py가 MCP 서버에 `BLOGOPS_ENGINE`, `BLOGOPS_MODEL`을 넘기고(`BLOGOPS_CYCLE_ID`처럼), `create_draft`가 초안 `meta.json`에 적는다. 비교와 교대 운영(5절)에서 어느 엔진이 쓴 초안인지 알아야 한다. 발행 커밋 본문(`content(ai)`)에 모델을 적을지는 열린 질문이다 (7절).

## 4. agy 가드레일

Claude Code에서 두 겹(settings.json + 실행 옵션)으로 막던 것을 agy에서 어떻게 막을지 정리한다. Claude 쪽 근거는 [ops/README.md](../ops/README.md) "Huninn용 Claude Code 설정 폴더"에 있다.

| Claude Code에서 | 막는 것 | agy에서 (계획) | 상태 |
| --- | --- | --- | --- |
| `CLAUDE_CONFIG_DIR=~/.config/huninn/claude` | 사람용 설정·로그인·기록을 같이 쓰는 것 | 실행할 때 `HOME=~/.config/huninn/agy`. 설정·로그인·MCP·기록이 모두 `$HOME/.gemini/` 아래에 생긴다. 사람용 `~/.gemini/antigravity-cli/settings.json`은 `toolPermission: always-proceed`에 `/home/hun/unattendant`를 신뢰하는 설정이라 Huninn이 읽으면 안 된다 | ❌ 옵션이 없다. `HOME`으로 되는지 시험 (T1) |
| `--tools ""` + `permissions.deny` | 셸, 파일 읽기·쓰기, 웹 | `permissions.deny`: `command(*)`, `read_file(*)`, `write_file(*)`, `read_url(*)`, `execute_url(*)`, `unsandboxed(*)`. `allow`: `mcp(blogops/*)`. `allowNonWorkspaceAccess` 끔, `enableTerminalSandbox: on` | ❌ 통째로 끄는 옵션이 없다. 무인 실행에서는 작업 폴더의 파일 읽기·쓰기가 자동 허용된다. deny가 그것까지 막는지 시험 (T3, T4) |
| `--system-prompt` | Claude Code 기본 프롬프트 대신 Huninn 지시 | 바꿀 수 없다. `prompt.md`와 사용자 메시지를 이어 붙여 `-p`로 넘긴다. agy 기본 프롬프트(코딩 에이전트)는 그대로 남는다 | ❌ 시험 (T5) |
| 작업 폴더를 레포 밖에, `claudeMdExcludes` | 사람 개발용 `CLAUDE.md`를 읽는 것 | 작업 폴더는 지금처럼 `~/.config/huninn/work`(비어 있음). `HOME`을 바꾸면 전역 rules(`~/.gemini/GEMINI.md`, `AGENTS.md`, `rules/*.md`)도 사람 것과 갈린다 | 시험 (T5) |
| `--mcp-config … --strict-mcp-config` | blogops 말고 다른 MCP | `--mcp-config` 같은 옵션이 없다. 사이클마다 `mcp.json`을 채워 `$HOME/.gemini/config/mcp_config.json`에 쓴다. 작업 폴더에 `.agents/mcp_config.json`은 없다 | 시험 (T2) |
| `--permission-mode dontAsk`, `disableBypassPermissionsMode` | 허용 목록 밖 툴, 권한 검사 끄기 | 무인 실행에서 승인이 필요한 툴은 거부되고(soft-deny) 사이클은 계속된다. `--dangerously-skip-permissions`는 절대 쓰지 않는다 | 문서 확인, 시험 (T3) |
| `--no-session-persistence`, `cleanupPeriodDays: 7` | 툴 출력이 담긴 대화 기록이 쌓이는 것 | 대화 기록(`conversations/`, `brain/`, `history.jsonl`)은 Huninn `HOME` 안에만 생긴다. 사이클이 끝나면 cycle.py가 지운다 | 어디에 무엇이 생기는지 시험 (T6) |
| `forceLoginMethod: claudeai`, usage credits 끔 | 의도하지 않은 과금 | `useG1Credits` 끔. 계정은 AI Pro 구독 계정 하나 | 설정 (T1) |
| `disableAllHooks` | 훅으로 셸 실행 | hooks·plugins·skills 폴더를 Huninn `HOME`에 만들지 않는다. 끄는 설정은 문서에 없다 | 시험 (T5) |
| `DISABLE_AUTOUPDATER=1` (systemd) | 실행 중 바이너리가 바뀌는 것 | 끄는 방법을 모른다. `~/.local/bin/agy`는 2026-10-22 04:02에 스스로 업데이트됐다 | ❌ 시험 (T8) |
| `--output-format json` | 결과·비용 기록 | `--output-format json`: `status`, `response`, `error`, `num_turns`, `duration_seconds`, `usage` | 문서 확인, 실제 필드 시험 (T2) |
| cycle.py 25분 제한 | 끝나지 않는 사이클 | 같다. `--print-timeout`도 명시한다(도움말 기본값 0초 = 무제한, 문서는 5분이라 다르다) | 시험 (T2) |
| `enableTelemetry` 없음 | — | `enableTelemetry` 끔, `showTips`·`showFeedbackSurvey` 끔 | 설정 |

**추가로 막을 것**

- **환경변수**: Claude처럼 사람 셸의 변수를 거른다. `GEMINI_`, `GOOGLE_`, `CLAUDE`, `ANTHROPIC_`으로 시작하는 변수는 넘기지 않고, `HOME`과 `PATH`만 정해서 넘긴다.
- **systemd**: `huninn-cycle.service`의 `ReadWritePaths`에 `~/.config/huninn`이 이미 있다. agy가 그 밖에 쓰는 곳(`~/.cache`, 키링 등)이 있으면 실행이 실패한다. 시험 (T7).
- **메모리**: `MemoryMax=1G`. Claude 실측 최댓값은 427.6MB(2026-10-12)였다. agy는 바이너리만 213MB라 다시 잰다 (T7).

## 5. 비교 방법

### 단계

1. **가드레일 시험** (T1~T8): blogops 없이, 그다음 blogops를 붙여 시험 실행(`BLOGOPS_NO_PUBLISH`)으로. 하나라도 막히지 않으면 다음 단계로 가지 않는다.
2. **같은 글감 블라인드 비교** (모래상자): 같은 상태에서 두 엔진이 같은 글감으로 초안을 하나씩 쓴다. 글감 3개 × 엔진 2개 = 6회.
3. **실운영 교대** (선택): 2단계 결과가 좋으면 Argon으로 1주 실제 사이클을 돈다. Phase 1이라 모든 글은 어차피 사람이 승인한다.

### 모래상자 (2단계)

시험 실행(`BLOGOPS_NO_PUBLISH`)도 지금은 진짜 `state/`에 초안을 쓰고 디스코드 #승인에 메시지를 보낸다. 두 엔진이 같은 상태에서 출발하려면 격리가 필요하다.

- **상태**: 작업실 레포의 git worktree를 `/tmp`(RAM)에 만들고 `BLOGOPS_ROOT`로 넘긴다. 사이트는 사본을 `BLOGOPS_SITE_DIR`로 넘긴다. 엔진마다 같은 커밋에서 새로 만든다.
- **알림**: `BLOGOPS_NO_NOTIFY`(새로 만든다)가 있으면 디스코드로 보내지 않고 모래상자의 `logs/notify.jsonl`에 쓴다.
- **글감 고정**: 사용자 메시지에 "이번 시험은 백로그 `<ID>`로 새 초안 하나만 쓴다"를 넣는다(`--item <ID>`, 새로 만든다). 프롬프트의 하루 순서 중 1(상태 점검)과 4(새 초안)만 하게 된다.
- **프롬프트**: 두 엔진 모두 같은 `prompt.md`를 쓴다. Gemini에 맞춰 고치면 그건 다른 변수라서, 고친 판은 따로 표시해 비교한다.

### 무엇을 재나

| 구분 | 지표 | 출처 |
| --- | --- | --- |
| 사람 평가 (블라인드) | 두 초안 중 더 나은 쪽, 툴 결과에 없는 주장(사실 오류) 수, 프롬프트 지시 위반(1인칭, 과장·감탄·이모지, 남의 일을 내 일로 쓰기), 한국어가 자연스러운지(번역투, AI 티) | 스크립트가 두 초안을 A/B로 섞어 보여 주고, 운영자가 표에 적는다 |
| 자동 | `check_quality` 첫 통과 여부, 툴 호출 수·오류 수, 거부된 도구 시도, 소요 시간, 토큰, 추정 비용, 쿼터·인증 오류, 최대 메모리 | `cycles.jsonl`, `logs/YYYY-MM-DD.jsonl`, systemd |

결과는 `experiments/engine-compare/`에 CSV로 남긴다(초안 본문은 비공개라 넣지 않고 점수와 지표만). 이 비교 자체가 운영기 글감이다.

### 판정

- Argon이 블라인드 비교에서 글감 3개 중 2개 이상 이기고, 사실 오류가 Claude보다 많지 않고, 가드레일·쿼터 문제 없이 돌면 → 기본 엔진을 `antigravity`로 바꾼다. Claude 경로는 남겨 되돌릴 수 있게 한다.
- 비기거나 지면 → `claude`를 유지한다. 비교 기록은 Phase 2 모델 선택 근거로 쓴다.
- 글은 Argon이 낫지만 쿼터 때문에 자주 끊기면 → B안(Gemini CLI + API 키)을 검토한다.

## 6. 시험·확인 목록

시험은 작업실에서 사람이 하고, 매장 타이머는 마지막에 바꾼다. 결과는 이 표 아래 "시험 기록"에 날짜와 함께 적는다.

### 사람이 먼저 할 일

| # | 할 일 | 왜 |
| --- | --- | --- |
| P1 | Claude 구독 토큰 재발급: `claude setup-token` → `~/.config/huninn/huninn.env`의 `CLAUDE_CODE_OAUTH_TOKEN` 교체 | 비교에는 Claude 사이클도 필요하다. 지금은 매일 실패하고 있다 |
| P2 | Huninn용 agy 로그인: `HOME=~/.config/huninn/agy agy`를 대화형으로 한 번 띄워 AI Pro 계정으로 로그인 | 무인 실행은 캐시된 자격증명만 쓴다. 브라우저 인증이 필요하다 (T1과 같이 한다) |
| P3 | Google Developer Program 혜택 활성화 ($10 크레딧) | B안으로 옮길 때를 대비한다. 넘친 만큼 청구되는지와 예산 알림 설정도 이때 확인한다 |
| P4 | Antigravity 쪽 AI credits 초과 사용 설정이 꺼져 있는지 확인 | 쿼터를 넘었을 때 돈이 나가지 않게 한다 |

### 시험 (작업실)

| # | 무엇을 | 어떻게 | 통과 기준 |
| --- | --- | --- | --- |
| T1 | **설정 폴더 분리** | `HOME=~/.config/huninn/agy`로 `agy`를 띄우고 로그인. 사람용 `~/.gemini/` 아래 파일의 수정 시각과 해시를 전후로 비교 | 설정·자격증명·기록이 모두 Huninn `HOME` 안에 생기고 사람용 `~/.gemini/`는 그대로다. 키링을 쓰려 하면 무엇으로 대체되는지 기록 |
| T2 | **무인 실행 기본** | 빈 작업 폴더에서 `agy -p "한 줄로 답해" --model gemini-4-argon-medium --output-format json --print-timeout 60s` | 종료 코드 0, `status: SUCCESS`, `usage` 필드가 있다. 실제 JSON 필드 이름을 기록해 `summarize`에 쓴다 |
| T3 | **셸 차단** | deny 규칙을 넣은 설정으로 "`cat /etc/hostname`을 실행해"를 요청 | 실행되지 않는다. stderr의 거부 안내를 기록 |
| T4 | **파일 읽기·쓰기 차단** | 작업 폴더 안 파일 읽기, 작업 폴더 밖 가짜 비밀값 파일(`~/.config/huninn/agy-test/fake.env`, 진짜 `huninn.env`는 쓰지 않는다) 읽기, 작업 폴더에 새 파일 쓰기를 각각 요청 | 셋 다 거부된다. 작업 폴더 안 읽기·쓰기가 deny로 막히지 않으면 blogops를 붙이지 않고 다른 방법(빈 읽기 전용 작업 폴더, `--sandbox`)을 찾는다 |
| T5 | **지시문 격리** | Claude 때(ops/README.md "구독 토큰으로 확인한 것")처럼 "보이는 지시문의 첫 문장"과 "쓸 수 있는 도구 목록"을 묻는다 | 사람용 rules나 `CLAUDE.md`·`GEMINI.md`·`AGENTS.md`가 보이지 않는다. 도구 목록에 셸·파일·웹이 없다(있어도 T3·T4에서 막히면 기록만 한다). agy 기본 프롬프트가 무엇을 말하는지 기록 |
| T6 | **기록 위치** | T2~T5 뒤 Huninn `HOME` 아래 새로 생긴 파일 목록 | 대화 기록 위치를 확인하고, cycle.py가 사이클 끝에 지울 경로를 정한다 |
| T7 | **systemd 아래에서** | 서비스와 같은 제한(`ProtectSystem=strict`, `ReadWritePaths`, `MemoryMax=1G`)으로 `systemd-run --user`나 임시 유닛에서 T2를 돌린다 | 쓰기 거부 없이 끝난다. 최대 메모리를 기록한다 |
| T8 | **자동 업데이트** | `agy` 설정·환경변수·`~/.gemini/antigravity-cli/updater/` 확인, `agy update --help` | 무인 실행 중 업데이트를 끄는 방법을 찾는다. 없으면 버전을 `cycles.jsonl`에 남겨 업데이트 전후를 구분한다 |
| T9 | **blogops 연결** | `mcp.json`을 채워 `$HOME/.gemini/config/mcp_config.json`에 쓰고 "blogops의 `get_system_health`를 불러"를 요청 | 툴 이름이 어떻게 보이는지(`blogops/get_system_health` 등) 확인. 호출이 `logs/YYYY-MM-DD.jsonl`에 사이클 ID와 함께 남는다 |
| T10 | **시험 사이클** | 모래상자에서 `--engine antigravity`로 사이클 1회 | 프롬프트의 하루 순서를 따르고, blogops 밖 도구를 쓰려 한 기록이 없고, `cycles.jsonl`에 기록이 남는다. 툴 호출 60회 상한이 동작한다 |
| T11 | **실패 신호** | 일부러 틀린 모델 이름, 로그인하지 않은 `HOME`으로 실행 | 0이 아닌 종료 코드나 `status` 오류가 나고, cycle.py가 #긴급(critical)으로 원인과 고치는 방법을 알린다 |
| T12 | **쿼터** | 비교 기간 내내 쿼터 오류가 났는지와 그 메시지 형식을 모은다 (일부러 일으키지 않는다) | 쿼터 오류를 인증 오류와 구분해 알린다 (쿼터는 warn, 다음 사이클에 다시) |

### 문서로 확인할 것

| # | 무엇을 | 왜 |
| --- | --- | --- |
| D1 | Antigravity(소비자 약관)가 스케줄러로 돌리는 무인 실행을 허용하는지 | plans 문서는 "scheduled tasks"를 기본 기능으로 들지만 약관 조항은 확인하지 못했다. Claude 쪽 판단은 claude-billing.md "약관" |
| D2 | agy 자격증명의 수명과 갱신 방식 | 이번 장애와 같은 일이 언제 생길지 알아야 한다 |
| D3 | AI Pro의 Antigravity 쿼터 수치 (`/usage`로 실제 확인) | 하루 1~6회 사이클이 쿼터 안에 드는지 |
| D4 | $10 크레딧이 AI Studio API 키 사용량에 빠지는지, 넘치면 청구되는지 | B안 비용 |

### 시험 기록

(아직 없음)

## 7. 열린 질문

- **엔진 실패 시 다른 엔진으로 대신 돌리기**: 한 엔진이 인증·쿼터 문제로 실패하면 다른 엔진으로 한 번 더 도는 기능. 이번 같은 장애를 사람 없이 넘길 수 있다(장애 자동 복구). 비교 기간에는 기록이 섞이니 비교가 끝난 뒤 정한다.
- **글에 모델을 밝힐지**: 모든 글에 AI 작성을 표시한다(architecture.md). 어떤 모델이 썼는지까지 글 하단이나 발행 커밋 본문에 적을지 정한다. 추천은 커밋 본문에만 적는 것이다(운영 레포가 공개라 추적은 된다).
- **effort**: Argon `medium`으로 시작한다. Claude는 지금 effort를 지정하지 않는다(기본값). 비교가 공정하려면 Claude 쪽 effort도 기록한다.
- **같은 하네스 비교**: agy에는 Claude Sonnet 5.5도 있어서 "같은 도구, 다른 모델" 비교도 할 수 있다. Google 쿼터를 쓰므로 2단계에서 필요할 때만 한다.

## 출처

- [Gemini CLI — Quotas and pricing](https://geminicli.com/docs/resources/quota-and-pricing/): Antigravity CLI로 대체(2026-06-18), Argon은 Antigravity에서
- [Gemini CLI — Authentication](https://geminicli.com/docs/get-started/authentication.md): 무인 실행은 API 키나 Vertex
- [Gemini CLI — Configuration](https://geminicli.com/docs/reference/configuration.md), [Policy engine](https://geminicli.com/docs/reference/policy-engine.md), [Headless](https://geminicli.com/docs/cli/headless.md): B안 설정
- [Antigravity CLI — Headless](https://antigravity.google/docs/cli/headless/): `-p`, JSON 필드, 캐시된 자격증명, 무인 실행의 권한 처리
- [Antigravity — Permissions](https://antigravity.google/docs/permissions/): `action(target)` 규칙, Deny > Ask > Allow
- [Antigravity — Settings](https://antigravity.google/docs/settings/): `toolPermission`, `allowNonWorkspaceAccess`, `useG1Credits`, `enableTelemetry`
- [Antigravity — Rules](https://antigravity.google/docs/rules/): rules 파일 위치와 로딩
- [Antigravity — Plans](https://antigravity.google/docs/plans/): Pro 쿼터(5시간 + 주간), BYOK 미지원, AI credits
- [Antigravity — Gemini CLI migration](https://antigravity.google/docs/cli/gcli-migration/): MCP 설정 위치, 자격증명 키링 이전
- [Gemini 4 Argon 모델](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon), [Gemini API 가격](https://ai.google.dev/gemini-api/docs/pricing): 모델 ID, 단가, 무료 등급 없음
- [Google blog — Developer Program premium in AI Pro/Ultra](https://blog.google/innovation-and-ai/technology/developers-tools/gdp-premium-ai-pro-ultra/) (2026-01-27): 월 $10 Cloud 크레딧
