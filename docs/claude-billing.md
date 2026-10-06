# Claude 사용 방식 비교: Pro 구독 vs API 크레딧

조사일: 2026-10-06. 가격·한도·약관은 바뀔 수 있으니 결정 전에 [출처](#출처)를 다시 확인한다.

**결정 (2026-10-06): Phase 1은 쓰고 있는 Pro 구독으로 돌리고 크레딧을 결제하지 않는다. Phase 2부터 API 크레딧으로 바꾼다.** Pro 구독은 Claude Code를 통해서만 쓸 수 있어서 Phase 1(C3)에는 쓸 수 있지만, Phase 2(C2, Messages API 자체 루프)에는 쓸 수 없다. 두 번째 Pro 구독은 사지 않는다.

## 두 방식

| | Pro 구독 | API 크레딧 (Claude Console) |
| --- | --- | --- |
| 결제 | 월 $20 (연 결제 시 월 $17, 부가세 별도) | 미리 충전한 크레딧에서 쓴 만큼 차감 |
| 계정 | claude.ai | platform.claude.com (별도 조직) |
| 쓸 수 있는 곳 | claude.ai 웹·앱, Claude Code (터미널, `claude -p`, 클라우드 세션) | 내 코드에서 직접 API 호출, Claude Code(API 키 인증), Agent SDK |
| Messages API 직접 호출 | **불가** | 가능 |
| 한도 | 5시간 단위 세션 한도 + 주간 한도. 토큰 수치는 공개되지 않음 ("Free의 5배 이상") | 내가 정한 월 지출 한도 (조직, 워크스페이스별) |
| 한도를 넘으면 | 리셋까지 멈춤. "usage credits"를 켜면 API 정가로 계속 사용 | 400 오류로 멈춤. 한도를 올리면 바로 재개 |
| 사람 사용량과의 관계 | claude.ai, Claude Code, 클라우드 세션이 같은 한도를 나눠 씀 | 워크스페이스로 분리 |

## Pro로 Huninn을 돌리는 방법 (가능한 범위)

Pro 계정으로 할 수 있는 무인 실행은 **Claude Code를 스크립트로 부르는 방식(C3)** 하나다.

```bash
# 한 번: 브라우저 인증 후 1년짜리 토큰 발급 (토큰은 저장되지 않으니 바로 .env에 넣는다)
claude setup-token
# 이후 cron/systemd에서
CLAUDE_CODE_OAUTH_TOKEN=... claude -p "오늘의 일간 루프를 실행해" --output-format json
```

- 공식 문서가 이 토큰을 "CI 파이프라인, 스크립트처럼 브라우저 로그인을 쓸 수 없는 환경"용으로 안내한다. Pro, Max, Team, Enterprise 플랜이 필요하다.
- 이 토큰은 모델 요청만 할 수 있다. Remote Control과 claude.ai 커넥터는 못 쓰고, 로컬에 설정한 MCP 서버는 쓸 수 있다.
- `--bare` 모드는 이 토큰을 읽지 않는다. 스크립트용으로 권장되는 모드라서, 이 모드를 쓰려면 API 키가 필요하다.
- `--output-format json` 결과에 `total_cost_usd`(정가 기준 추정 비용)가 나온다. 구독으로 돌려도 "글당 비용"을 추정치로는 남길 수 있다.

**Pro로 할 수 없는 것**

- **C2 자체 루프**: Messages API를 직접 부르는 코드는 API 키로만 인증된다. Phase 2부터는 어차피 크레딧이 필요하다.
- **Agent SDK로 만든 에이전트에 구독 로그인 쓰기**: Agent SDK 문서에 "사전 승인 없이는 Agent SDK로 만든 에이전트를 포함한 제품에 claude.ai 로그인이나 구독 한도를 쓰게 할 수 없다. API 키 인증을 쓰라"는 안내가 있다.

## 비교

| 기준 | Pro 구독 (C3) | API 크레딧 |
| --- | --- | --- |
| 월 비용 | 고정 $20. 이미 내고 있다면 추가 비용 0 | 사용량만큼. 추정 월 $10(Sonnet 5.5)~$20(Opus 5.5) |
| 아키텍처 단계 | Phase 1만 | Phase 1~3 전부 |
| 멈추는 방식 | 5시간·주간 한도에 걸리면 리셋까지 멈춘다. 사람이 쓴 사용량 때문에 Huninn이 멈출 수도 있다 | 내가 정한 금액에서만 멈춘다 |
| 인증 만료 | `setup-token`이 1년마다 만료. 갱신에 브라우저 인증(사람)이 필요 | 키 만료일을 직접 정한다(무기한 가능). 만료 7일 전 이메일 |
| 비용 기록 | `total_cost_usd` 추정치. 실제로 청구되는 돈은 아니다 | API 응답의 `usage`가 실제 청구와 일치 |
| 사람 작업과의 간섭 | 같은 한도를 나눠 쓴다 | 없음 |
| 프롬프트 캐시 수명 | 구독 1시간, usage credits 사용 중에는 5분 | 기본 5분 (1시간 선택 가능, 쓰기 단가가 더 높음) |
| 약관 | 아래 참고 | 자동화 허용 |

### 약관

- Anthropic 소비자 약관(2025-10-08 시행)은 "Anthropic API 키로 접속하는 경우나 Anthropic이 명시적으로 허용한 경우를 제외하고, 봇·스크립트 등 자동화된 방식으로 서비스에 접속하지 않는다"고 정한다.
- Claude Code 문서는 구독 토큰(`setup-token`)을 스크립트·CI용으로 공식 안내하므로, **Claude Code를 통한 스크립트 실행은 허용된 범위로 보인다.** 다만 24시간 무인 에이전트가 이 범위에 들어가는지는 문서에 명시돼 있지 않다.
- 한도를 피하려고 구독을 두 개 쓰는 것을 금지하는 조항은 이번 조사에서 찾지 못했다. 그래도 계정 하나를 사람용, 하나를 봇용으로 나누는 건 위 자동화 조항의 회색지대를 두 배로 넓히는 일이라 권하지 않는다.

## 비용 추정 (API)

토큰 양은 가정이고, Phase 1에서 실측으로 바꾼다. 단가는 [가격표](https://claude.com/pricing) 기준(입력/출력, 100만 토큰당).

| 항목 | 월 토큰 가정 | Sonnet 5.5 ($2/$10) | Opus 5.5 ($4/$20) |
| --- | --- | --- | --- |
| 일간 점검·기획 30회 | 입력 60만, 출력 6만 | $1.8 | $3.6 |
| 글 18편 (영어판 포함) | 입력 180만, 출력 27만 | $6.3 | $12.6 |
| 주간 보고서 4회 | 입력 40만, 출력 6만 | $1.4 | $2.8 |
| 실험 예약·결과 해석 30회 | 입력 90만, 출력 9만 | $2.7 | $5.4 |
| **합계** | | **약 $12** | **약 $24** |

- **더 나올 수 있는 이유**: 툴을 부를 때마다 대화 전체를 다시 보낸다. Opus 5.5와 Sonnet 5.5는 thinking을 끌 수 없고, thinking 토큰은 출력 요금으로 청구된다. 품질 게이트에서 최대 2회 다시 쓴다.
- **덜 나올 수 있는 이유**: 매번 같은 앞부분(시스템 프롬프트, 툴 정의, 전략 문서)은 캐시 읽기 단가($0.20)가 적용된다. Phase 1은 글이 5개 정도다.
- **실험 비용 원칙**: 대기·재시도·집계는 Pi 코드가 하고, Claude는 예약과 해석만 한다. Claude가 실험 완료를 10분마다 확인하는 구조라면 이것만으로 월 $260(Sonnet 5.5)까지 갈 수 있다.

## 선택지와 추천

| 선택지 | 판단 |
| --- | --- |
| A. API 크레딧만 (워크스페이스 한도 월 $20~30) | 처음 추천안. 처음부터 Phase 2와 같은 인증·비용 기록으로 시작한다 |
| B. Phase 1은 지금 Pro로, Phase 2부터 API | **채택 (2026-10-06).** 남는 Pro 사용량을 쓰고, Phase 1 동안 크레딧이 들지 않는다. 대신 Phase 1의 비용 기록은 추정치이고, 사람 작업과 한도를 나눠 쓴다 |
| C. Pro를 하나 더 구독해서 봇 전용으로 | 비추천. Phase 2에서 못 쓰고, 고정 $20이 API 추정치와 비슷하거나 비싸다 |
| D. Pro + usage credits | Huninn용으로는 의미 없음. 한도를 넘은 만큼 API 정가로 내는 것이라 A와 비용은 같고, 사람 사용량과 섞인다 |

B를 고른 이유: Phase 1은 글 5개 정도에 모든 글을 사람이 승인하는 검증 단계라 사용량이 작다. 인증 방식(`CLAUDE_CODE_OAUTH_TOKEN` → `ANTHROPIC_API_KEY`)은 환경변수 하나만 바꾸면 되므로, A의 "처음부터 같은 인증" 장점이 크지 않다.

### Phase 1을 Pro로 돌릴 때 지킬 것

1. **usage credits를 끈다.** claude.ai Settings → Usage의 usage credits가 켜져 있으면 한도를 넘은 사용량이 API 정가로 결제된다. "크레딧을 쓰지 않는다"는 결정은 이 설정이 꺼져 있어야 지켜진다.
2. **토큰은 `claude setup-token`으로 발급해 `.env`의 `CLAUDE_CODE_OAUTH_TOKEN`에 둔다.** 1년 뒤 만료되고, 갱신에는 브라우저 인증이 필요하다. 만료일을 todo.md에 적는다.
3. **gitleaks 규칙을 먼저 추가한다.** 2026-10-06에 `anthropic-credential` 규칙을 추가했다. 기본 규칙은 API 키·Admin 키 형식만 잡아서 구독 토큰이 그대로 커밋됐다. 발급 뒤 `.env`를 값을 가린 채 검사해 실제 토큰이 걸리는지 확인한다 ([pre-commit.md](pre-commit.md)).
4. **Huninn 전용 `CLAUDE_CONFIG_DIR`을 쓴다.** 구독 토큰은 `--bare` 모드에서 읽히지 않아서, 그대로 두면 Huninn이 사람이 쓰는 `~/.claude`의 hook·플러그인·설정을 함께 읽는다. 폴더는 `~/.config/huninn/claude`에 만들었고, 레포 `CLAUDE.md`는 이 방법으로 분리되지 않는다 ([ops/README.md](../ops/README.md)).
5. **비용은 추정치로 기록한다.** `total_cost_usd`를 사이클마다 남기되 `estimate: true`로 표시해 Phase 2의 실제 청구 비용과 섞지 않는다.
6. **사이클당 툴 호출 상한은 그대로 둔다.** 구독 한도 안이라 돈은 더 나가지 않지만, 루프가 꼬이면 사람이 쓸 한도를 다 쓴다. 한도에 걸려 멈추면 #긴급으로 알린다.

### Phase 2 준비: Console 설정 절차

Phase 2 시작 직전에 [Claude Console](https://platform.claude.com)에서 한다.

1. **Settings → Billing**: 크레딧 충전, Spend limits에서 조직 월 한도 설정 (등급 상한보다 낮게).
2. **Settings → Workspaces → Create workspace** (`unattendant`): Default 워크스페이스에는 한도를 걸 수 없어서 전용 워크스페이스가 필요하다. Spend limits 탭에서 월 한도와 알림 기준을 정한다.
3. **Settings → Service accounts**: `huninn` 서비스 계정을 만들고 `unattendant` 워크스페이스에 추가한다. 무인 작업에는 사람 계정에 묶인 개인 키보다 서비스 계정 키가 권장된다.
4. **Settings → API keys → Create key**: Linked account는 서비스 계정, 워크스페이스는 `unattendant`로 한정, 만료는 직접 정한다(만료 7일 전 이메일).
5. **Pi**: 키를 화면에 남기지 않고 `.env`에 넣는다. `read -rsp "API key: " K && printf 'ANTHROPIC_API_KEY=%s\n' "$K" >> .env && unset K && chmod 600 .env`. 그다음 `CLAUDE_CODE_OAUTH_TOKEN`을 지운다.

**만료 예정인 클라우드 세션 크레딧(Pro 계정)** 은 API 호출에는 못 쓴다. 클라우드 세션(claude.ai/code, `claude --cloud`, Routines)에만 적용된다. Huninn의 코드를 만드는 개발 작업(Hugo 템플릿, `blogops`, 테스트)을 클라우드 세션으로 돌려서 소진하는 데 쓴다.

## 앞선 답변 정정 (2026-10-06 대화)

조사 전 대화에서 아래처럼 말했는데, 문서를 확인해 보니 사실과 달랐다.

| 앞선 답변 | 실제 |
| --- | --- |
| 구독으로 돌리면 글당 비용을 정확히 남길 수 없다 | `claude -p --output-format json`이 `total_cost_usd` 추정치를 준다. 다만 실제 청구액은 아니다 |
| 구독 로그인이 만료되면 사람이 다시 로그인해야 한다 | `claude setup-token`으로 1년짜리 토큰을 쓸 수 있다. 1년마다 한 번은 사람이 갱신한다 |
| 소비자 약관상 봇 사용이 문제될 수 있다 | 자동화 금지 조항은 있지만, Claude Code 문서가 구독 토큰의 스크립트 사용을 공식 안내한다. Claude Code를 통한 실행은 허용 범위로 보이고, 24시간 무인 운영 여부는 명시돼 있지 않다 |

결론(API 크레딧 추천)은 바뀌지 않는다. 가장 큰 이유인 "Phase 2의 Messages API 자체 루프는 API 키로만 돌아간다"는 그대로다.

## 출처

- [Claude Code — Authentication](https://code.claude.com/docs/en/authentication): 인증 우선순위, `claude setup-token`(1년 토큰), 구독 토큰의 쓰임
- [Claude Code — Run Claude Code programmatically](https://code.claude.com/docs/en/headless): `claude -p`, `--bare`, `total_cost_usd`
- [Claude Code — Manage costs](https://code.claude.com/docs/en/costs): 구독의 5시간·주간 한도, usage credits, 캐시 수명
- [Claude Code — Use Claude Code in the cloud](https://code.claude.com/docs/en/claude-code-on-the-web): 클라우드 세션
- [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview): Agent SDK에서 claude.ai 로그인 사용 제한
- [Anthropic 소비자 약관](https://www.anthropic.com/legal/consumer-terms): 자동화 접속 조항 (2025-10-08 시행)
- [Claude 가격](https://claude.com/pricing): Pro 가격, 한도 설명, API 단가
- [Claude API — Rate limits](https://platform.claude.com/docs/en/api/rate-limits): 지출 한도, 한도 도달 시 동작
- [Claude API — Authentication](https://platform.claude.com/docs/en/manage-claude/authentication): 키 종류, 서비스 계정 키, 만료
- [Claude API — Workspaces](https://platform.claude.com/docs/en/manage-claude/workspaces): 워크스페이스별 지출 한도 (Default 워크스페이스는 불가)
