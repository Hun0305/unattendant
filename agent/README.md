# agent

Huninn이 시스템을 건드리는 통로인 blogops. 설계는 [docs/blogops.md](../docs/blogops.md).

## 지금 있는 것 (만드는 순서 1\~3단계)

| 파일 | 역할 |
| --- | --- |
| `blogops/config.py` | 경로(체크아웃 루트 기준)와 한도 |
| `blogops/store.py` | 초안·승인 기록 파일, 해시, 상태 계산 |
| `blogops/frontmatter.py` | 초안 front matter 쓰기·읽기 (JSON 문법 값. Hugo가 YAML로 읽는다) |
| `blogops/log.py` | `logs/YYYY-MM-DD.jsonl` 기록 |
| `blogops/review.py` | 사람용 승인·반려 명령 |
| `blogops/records.py` | 공개 기록 읽기(허용 목록: `docs/*.md`, `ops/README.md`, `site/README.md`), 커밋 메시지, 발행된 글 목록 |
| `blogops/publish.py` | 발행 (docs/blogops.md 5절): 승인된 그 버전만, 하루 1편, 임시 빌드 → 실제 빌드, 작성자 Huninn 커밋, push(겹치면 rebase 후 재시도), 공개 URL 확인. 실패하면 되돌린다 |
| `blogops/backlog.py` | 글감 상태 변경과 추가 (`state/backlog.json`) |
| `blogops/fileio.py` | 원자적 쓰기와 잠금 (초안·승인·백로그 공용) |
| `blogops/quality.py` | 품질 검사 (docs/blogops.md 6절): front matter, 시리즈, 분량, 출처, 레포 링크, 내부 IP·MAC·이메일, 중복, gitleaks, Hugo 빌드 |

초안 상태는 저장하지 않고 지금 내용의 해시와 기록을 대조해 계산한다. 승인 뒤 내용이 바뀌면 승인이 자동으로 풀린다.

## 승인·반려 (사람)

```bash
ops/huninn/review list
ops/huninn/review show <초안ID> --body
ops/huninn/review approve <초안ID>
ops/huninn/review reject <초안ID> "사유"
```

래퍼가 들어 있는 체크아웃의 `state/`를 다룬다. 운영에서는 매장(`~/unattendant-live`)의 래퍼를 쓴다.

## 테스트

```bash
cd agent && python3 -m unittest discover -s tests -v
```

`test_quality.py`의 도구 통합 테스트는 gitleaks와 hugo가 있어야 돈다. 사이트 위치는 `BLOGOPS_SITE_DIR`로 바꿀 수 있다(기본은 `<루트>/site`).

지금은 표준 라이브러리만 쓴다. MCP 서버(5단계)를 만들 때 `agent/.venv`에 MCP Python SDK를 설치한다.
