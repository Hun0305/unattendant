# blogops 작업 보고서 (feat/blogops, 2026-10-07)

> 임시 문서. 2026-10-07 아침에 읽으려고 남겼다. CLAUDE.md 문서 목록에는 넣지 않았다. 다 읽으면 지우거나, 필요한 내용만 todo.md나 PR 설명으로 옮긴다.
>
> 만든 방법: 브랜치 커밋 11개의 본문, docs/blogops.md(설계), docs/todo.md(진행)를 바탕으로 정리했다. 코드는 설계와 다를 만한 곳만 골라 확인했다.

## 한 줄 요약

blogops의 만드는 순서 1~5단계 코드는 다 썼고 테스트 69개가 통과한다. 남은 것은 5단계의 완료 기준인 **Pi에서 실제로 한 번 돌려 초안과 승인 요청까지 확인**하는 일이다. 그다음이 6단계(운영 위치 분리와 타이머)다.

## 브랜치 상태

- 브랜치: `feat/blogops`, main(`a4eff73`) 위에 커밋 11개. 2026-10-07 새벽에 PR로 main에 squash merge했다. 이 보고서도 그때 같이 들어갔다.
- 변경: 파일 41개, 약 3,800줄 추가.
- 테스트: 69개 통과. 클라우드 세션에서 TZ=UTC와 Asia/Seoul로 돌렸고, Pi와 같은 버전의 hugo 0.167.0과 gitleaks 8.30.1이 필요한 테스트까지 포함했다.

| 커밋 | 내용 |
| --- | --- |
| `34618aa` | 전략 문서 1판(`state/strategy.md`), 백로그 글감 7개(`state/backlog.json`) |
| `756f1a3` | todo에 state 뼈대 체크 |
| `c4bf437` | 설계 문서 `docs/blogops.md` |
| `14b1a97` | 1단계: 초안·승인 기록(`store`), 사람용 `review` 명령 |
| `463bd37` | 2단계: 공개 기록 읽기(`records`), 품질 검사(`quality`) |
| `72ef781` | 3단계: 발행(`publish`), 백로그(`backlog`) |
| `3b99d4f` | 4단계: 디스코드 알림(`notify`), IndexNow, 툴 호출 상한 |
| `b17decf` | 테스트 수정: `git_log` 테스트를 KST 날짜로 비교 |
| `f7fc124` | 전략 문서에서 Phase 1에 없는 `update_strategy` 언급을 고침 |
| `969d974` | 5단계: MCP 서버, 하루 사이클 실행, 시스템 프롬프트 |
| `f99a33a` | todo: 5단계는 작성 완료, 실행 시험만 남음 |

## 단계별로 한 일

### 준비: 전략과 설계

- **전략 1판**: 하루 1편 목표. 출처 있는 재료가 없는 날은 쓰지 않고 이유를 남긴다. Phase 1은 운영기와 주간 보고서만 쓴다.
- **백로그**: 지금 쓸 수 있는 운영기 4개(이름 짓기, 서빙 구조, Pi에서 gitleaks 35초, AI 운영 사이트 19곳)와 대기 중인 3개.
- **설계(`docs/blogops.md`)**: 툴 18개, 한도(승인 대기 1개, 하루 발행 1편, 사이클당 툴 호출 60회, 품질 3번 실패 시 보류), 파일 형식과 해시. 결정 세 가지는 승인 다음 날 발행, 사이클 14:00 KST, 작업실과 매장 분리다.

### 1단계: 초안·승인 기록과 `review`

- 초안 상태는 저장하지 않는다. 지금 내용의 해시를 기록과 대조해 계산한다. 그래서 승인 뒤 내용이 바뀌면 승인이 자동으로 풀린다.
- 사람은 `ops/huninn/review list|show|approve|reject`로 처리한다. 반려 사유는 필수다.

### 2단계: 공개 기록 읽기와 품질 검사

- Huninn은 허용 목록(`docs/*.md`, `ops/README.md`, `site/README.md`)에 있는 파일만 읽는다. 심볼릭 링크를 따라간 실제 위치도 목록 안이어야 한다.
- 품질 검사는 자동으로 볼 수 있는 것만 본다. 사실이 맞는지는 사람이 승인할 때 본다.
- 만들면서 버그 2개를 잡고 테스트로 고정했다. 하나는 docs/ 안의 심볼릭 링크로 `.env`를 읽을 수 있던 것, 다른 하나는 링크 주소 속 숫자 때문에 출처를 요구하던 것이다.

### 3단계: 발행과 백로그

- 승인된 그 버전만, 하루 1편만 발행한다. 임시 빌드가 되면 실제 빌드를 하고, 작성자 `Huninn`, 메시지 `content(ai)`로 커밋한 뒤 push하고 공개 URL을 확인한다.
- 빌드나 커밋이 실패하면 복사한 글을 지우고 다시 빌드한다.
- 실제 사이트 레포의 사본으로 품질 검사 → 승인 → 발행까지 끝까지 돌려 봤다. 실제 사이트와 GitHub에는 변경이 없었다.

### 4단계: 알림, IndexNow, 툴 호출 상한

- 디스코드는 봇 REST API로 메시지만 보낸다. info는 #일일요약, warn과 critical은 #긴급(critical만 멘션), 승인 요청은 #승인(멘션)으로 간다.
- 실제 3채널 전송을 확인했다.
- IndexNow는 운영자 결정으로 뒤로 미뤘다. 키 파일이 없으면 툴이 건너뛴다.

### 5단계: MCP 서버와 하루 사이클 (작성 완료, 실행 시험 남음)

- **`server.py`**: MCP 서버(stdio). 설치된 SDK가 mcp 2.x라 `FastMCP` 대신 `MCPServer`를 쓴다.
  - 툴 18개는 다른 모듈을 부르기만 한다.
  - 오류는 `ok: false` 결과로 돌려준다.
  - 호출마다 사이클 ID와 함께 기록한다. 긴 본문은 길이만 남긴다.
- **`cycle.py`, `run-cycle.sh`**: `claude -p`에 blogops 툴만 주고 레포 밖 `~/.config/huninn/work`에서 돌린다.
  - 모델을 고정하고, 구독 토큰만 넘긴다.
  - 한 번에 하나만 돌고, 25분이 지나면 멈춘다.
  - 결과는 `logs/cycles.jsonl`에 남기고, 실패하면 #긴급으로 알린다.
- **`prompt.md`**: 원칙, 하루 순서, 글쓰기 규칙, 주간 보고서 지시.
- **`health.py`, `summary.py`**: 상태 점검과 주간 보고서 재료.
- **확인한 것**: Pi에서 MCP 프로토콜로 툴 목록, 입력 형식, 오류 결과, 기록을 확인했다. 가짜 claude로 실행 옵션, 넘기는 환경변수, 실패 알림, 시간 제한을 테스트했다.

## 어젯밤 클라우드 세션에서 바뀐 것

Pi 세션이 사용 한도(03:40 리셋)에 걸려 멈췄다. 운영자가 `7a2823e 단계 5 임시 커밋`을 push했고, 클라우드 세션에서 이어 마무리했다.

- **임시 커밋 정리**: 커밋 규칙에 맞는 3개(`b17decf`, `f7fc124`, `969d974`)로 다시 써서 `--force-with-lease`로 push했다. 옛 커밋 `7a2823e`는 Pi 레포에 남아 있다.
- **백로그 변경 제외**: 임시 커밋에 있던 `state/backlog.json` 변경은 뺐다. 시험 사이클의 `create_draft`가 `gitleaks-on-pi`를 `drafting`으로 바꾸고 JSON 줄바꿈을 다시 쓴 것이었다.
- **더한 수정**:
  - `cycle.py`가 셸에 있는 `CLAUDE_CONFIG_DIR`을 무시하고 늘 `~/.config/huninn/claude`를 쓴다. 사람용 설정과 hook이 섞일 여지를 없앴다.
  - 본문 h1 규칙 테스트를 추가했다.
  - `git_log` 테스트가 KST 날짜로 비교한다. 전에는 UTC 환경에서 KST 00~09시에 실패했다.
  - ops/README의 실행 옵션을 실제 명령으로 확정했다.
  - todo에서 "실행 스크립트·mcp.json"과 "비용 로그"를 체크했다.

## 설계와 다른 점, 아직 없는 것

설계 문서 자체는 고치지 않았다. 고칠지는 운영자가 정한다.

| 항목 | 설계 | 지금 |
| --- | --- | --- |
| 코드 구조 (blogops.md 8절) | 모듈 10개, `run-cycle.sh`가 `claude -p` 실행과 비용 기록 | 모듈 18개(`env`, `httpjson`, `fileio`, `frontmatter`, `backlog`, `health`, `summary`, `cycle` 추가). 실행은 `cycle.py`가 하고 `run-cycle.sh`는 감싸기만 한다. 파일 목록은 `agent/README.md`에 있다 |
| architecture.md 툴 표 (blogops.md 2절) | 설계가 확정되면 새 툴 6개를 반영 | 아직 반영하지 않았다 |
| state/ 변경 push (blogops.md 7절) | Huninn이 매장에서 `state/` 변경을 운영 레포에 push | 발행 커밋은 사이트 레포에만 한다. 백로그 상태 변경 같은 `state/` 변경을 커밋·push하는 코드는 없다. 6단계에서 정해야 한다 |
| 사이클 시작 동기화 (blogops.md 7절) | 두 레포를 `git pull --ff-only` 하고 사이트가 바뀌었으면 다시 빌드 | 아직 없다. 6단계 |
| 시간 제한 (blogops.md 1절) | systemd 30분 | `cycle.py`의 25분만 있다. systemd 유닛은 6단계 |
| 백로그 파일 형식 | 운영자가 손으로 쓴 형식(목록을 한 줄에) | blogops가 저장할 때 들여쓰기 형식으로 다시 쓴다. Huninn이 처음 쓸 때 파일 전체가 바뀐 것처럼 보인다 |

todo에서 체크하지 않은 것 중 사실상 끝난 것이 있다. 체크할지 운영자가 정한다.

- **"Huninn 커밋 작성자를 Huninn으로"**: `publish.py`에 들어 있고, 사이트 사본 시험에서 확인했다.
- **"승인 흐름"**: `review` 명령, 해시, #승인 알림이 다 있다. Huninn이 실제로 승인을 요청하는 건 5단계 실행 시험에서 확인된다.

## 오늘 할 일 (순서대로)

1. **Pi 맞추기**: blogops는 main에 합쳐졌고 원격 `feat/blogops` 브랜치는 지웠다.
   ```bash
   cd ~/unattendant && git pull --ff-only          # 작업실(main)
   cd ~/unattendant-worktrees/blogops
   git status   # 바뀐 게 없거나 state/backlog.json만 있으면 정상
   git fetch origin main && git reset --hard origin/main
   ```
   - 작업 트리의 로컬 `feat/blogops`가 main과 같아진다.
   - `logs/`, `state/drafts/`, `agent/.venv`는 git이 다루지 않아서 그대로 남는다. 그래서 시험은 이 작업 트리에서 하면 된다.
   - 6단계는 새 브랜치(`feat/` 또는 `ops` 작업)에서 시작한다.
2. **첫 시험 사이클 결과 보기**
   - `logs/cycles.jsonl` 마지막 줄과 디스코드 #승인·#긴급을 본다.
   - 시험 사이클도 Pi 세션과 같은 Pro 한도를 써서 중간에 멈췄을 수 있다. 그랬다면 #긴급에 실패 알림이 와 있다.
3. **시험 초안 정리**: `ops/huninn/review list`로 보고 지운다. 승인 대기로 남아 있으면 새 승인 요청이 막힌다.
4. **실행 시험 (5단계 마무리)**: 명령과 기대 결과는 todo.md 5단계 항목에 적어 두었다.
   ```bash
   BLOGOPS_NO_PUBLISH=1 BLOGOPS_SITE_DIR=~/unattendant/site BLOGOPS_ENV_FILE=~/unattendant/.env ops/huninn/run-cycle.sh
   ```
   한도가 리셋된 뒤에, 사람이 Claude Code를 많이 쓰지 않을 때 돌린다. 둘이 같은 한도를 나눠 쓴다.
5. **blogops 툴만 보이는지 확인**: todo "실행 확인"의 남은 항목.
6. 위가 끝나면 todo 5단계를 체크하고 6단계(운영 위치 분리)를 시작한다.

## 정할 것

- 위 "설계와 다른 점"을 docs/blogops.md에 반영할지. 특히 `state/` 변경 push 방식은 6단계 전에 정해야 한다.
- 이 보고서를 지울지 (main에 들어가 있다).
