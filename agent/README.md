# agent

Huninn이 시스템을 건드리는 통로인 blogops. 설계는 [docs/blogops.md](../docs/blogops.md).

## 지금 있는 것 (만드는 순서 1단계)

| 파일 | 역할 |
| --- | --- |
| `blogops/config.py` | 경로(체크아웃 루트 기준)와 한도 |
| `blogops/store.py` | 초안·승인 기록 파일, 해시, 상태 계산 |
| `blogops/frontmatter.py` | 초안 front matter 쓰기·읽기 (JSON 문법 값. Hugo가 YAML로 읽는다) |
| `blogops/log.py` | `logs/YYYY-MM-DD.jsonl` 기록 |
| `blogops/review.py` | 사람용 승인·반려 명령 |

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

지금은 표준 라이브러리만 쓴다. MCP 서버(5단계)를 만들 때 `agent/.venv`에 MCP Python SDK를 설치한다.
