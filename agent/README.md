# agent

Huninn이 시스템을 건드리는 통로인 blogops. 설계는 [docs/blogops.md](../docs/blogops.md).

## 지금 있는 것 (만드는 순서 1\~5단계)

| 파일 | 역할 |
| --- | --- |
| `blogops/config.py` | 경로(체크아웃 루트 기준)와 한도 |
| `blogops/store.py` | 초안·승인 기록 파일, 해시, 상태 계산 |
| `blogops/frontmatter.py` | 초안 front matter 쓰기·읽기 (JSON 문법 값. Hugo가 YAML로 읽는다) |
| `blogops/log.py` | `logs/YYYY-MM-DD.jsonl` 기록, 사이클당 툴 호출 상한(`CycleGuard`) |
| `blogops/review.py` | 사람용 승인·반려 명령 |
| `blogops/records.py` | 공개 기록 읽기(허용 목록: `docs/*.md`, `ops/README.md`, `site/README.md`), 커밋 메시지, 발행된 글 목록 |
| `blogops/publish.py` | 발행 (docs/blogops.md 5절): 승인된 그 버전만, 하루 1편, 임시 빌드 → 실제 빌드, 작성자 Huninn 커밋, push(겹치면 rebase 후 재시도), 공개 URL 확인. 실패하면 되돌린다 |
| `blogops/backlog.py` | 글감 상태 변경과 추가 (`state/backlog.json`) |
| `blogops/notify.py` | 디스코드 알림 (봇 REST API, 상주 프로세스 없음): info → #일일요약, warn·critical → #긴급(critical은 멘션), 승인 요청 → #승인(멘션, review 명령 안내) |
| `blogops/indexnow.py` | IndexNow 색인 요청. 키 파일은 `site/static/<키>.txt`(공개) |
| `blogops/env.py` | 비밀값 읽기 (`BLOGOPS_ENV_FILE` → `~/.config/huninn/huninn.env` → `<루트>/.env`). 값은 출력·기록하지 않는다 |
| `blogops/httpjson.py` | JSON POST |
| `blogops/fileio.py` | 원자적 쓰기와 잠금 (초안·승인·백로그 공용) |
| `blogops/quality.py` | 품질 검사 (docs/blogops.md 6절): front matter, 시리즈, 분량, 출처, 레포 링크, 내부 IP·MAC·이메일, 중복, gitleaks, Hugo 빌드 |
| `blogops/health.py` | 상태 점검: 디스크, CPU 온도, 메모리, 사이트 응답, 마지막 빌드, 초안 상태별 수 |
| `blogops/summary.py` | 주간 보고서 재료: 발행, 승인·반려와 사유, 품질 검사 첫 통과율, 보류, 사이클 수와 추정 비용 |
| `blogops/server.py` | MCP 서버(stdio). 툴 18개는 위 모듈을 부르기만 한다. 툴 오류는 `ok: false` 결과로 돌려주고, 호출마다 로그를 남긴다 |
| `blogops/cycle.py` | 하루 사이클 실행: `claude -p`를 blogops 툴만 쥐여 돌리고 `logs/cycles.jsonl`에 기록, 실패하면 #긴급 |

초안 상태는 저장하지 않고 지금 내용의 해시와 기록을 대조해 계산한다. 승인 뒤 내용이 바뀌면 승인이 자동으로 풀린다.

## 승인·반려 (사람)

```bash
ops/huninn/review list
ops/huninn/review show <초안ID> --body
ops/huninn/review approve <초안ID>
ops/huninn/review reject <초안ID> "사유"
```

래퍼가 들어 있는 체크아웃의 `state/`를 다룬다. 운영에서는 매장(`~/unattendant-live`)의 래퍼를 쓴다.

## 하루 사이클 (Huninn)

```bash
ops/huninn/run-cycle.sh --show                   # 실행할 명령과 MCP 설정만 본다
ops/huninn/run-cycle.sh                          # 한 번 돌린다
BLOGOPS_NO_PUBLISH=1 ops/huninn/run-cycle.sh     # 시험 실행: publish_post가 거부된다
```

- 지시는 `ops/huninn/prompt.md`(시스템 프롬프트), 툴은 `ops/huninn/mcp.json`(서버 이름 `blogops`), 권한은 `ops/huninn/settings.json`이다.
- 레포 밖 `~/.config/huninn/work`에서 돌고, 비밀값 파일에서 구독 토큰만 꺼내 넘긴다. `BLOGOPS_`로 시작하는 환경변수는 MCP 서버에도 넘어간다.
- 모델은 `claude-sonnet-5-5`로 고정했다. `HUNINN_MODEL` 또는 `--model`로 바꾼다.
- 사이클마다 `logs/cycles.jsonl`에 소요 시간, 턴 수, 툴 호출 수, 추정 비용(`total_cost_usd`, `estimate: true`)을 남긴다. 툴 호출 하나하나는 `logs/YYYY-MM-DD.jsonl`에 사이클 ID와 함께 남는다.

## 설치와 테스트

```bash
cd agent && python3 -m venv .venv && .venv/bin/pip install -e .   # MCP Python SDK(mcp)
.venv/bin/python -m unittest discover -s tests -v
```

`test_server.py`는 mcp가 있어야 돈다(시스템 `python3`으로 돌리면 건너뛴다). `test_quality.py`의 도구 통합 테스트는 gitleaks와 hugo가 있어야 돈다. 사이트 위치는 `BLOGOPS_SITE_DIR`로 바꿀 수 있다(기본은 `<루트>/site`).
