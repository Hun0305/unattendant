# blogops 설계 (Phase 1)

blogops는 Huninn이 시스템을 건드리는 유일한 통로다. Python 라이브러리와, 그것을 툴로 내보이는 MCP 서버(stdio)로 이뤄진다. Huninn(`claude -p`)은 기본 도구 없이 blogops 툴만 쓸 수 있고(`ops/huninn/settings.json`), 품질·승인·발행 한도 같은 조건은 전부 blogops가 서버 쪽에서 검사한다.

이 문서는 Phase 1에서 만드는 범위와 파일 형식을 정한다. 설계 근거는 [architecture.md](architecture.md)(툴 스펙, 가드레일), 승인에 관한 결정은 [todo.md](todo.md) Phase 1 "먼저 정할 것"에 있다.

## 1. 하루 사이클

systemd 타이머가 매일 14:00(KST)에 `claude -p`를 한 번 돌린다. Huninn이 따를 순서는 시스템 프롬프트(`ops/huninn/prompt.md`, 공개)에 적는다.

1. **상태 점검**: `get_system_health`. 이상이 있으면 `notify_human`으로 알리고 새 글은 쓰지 않는다.
2. **승인된 초안 발행**: `list_drafts`에서 승인된 초안이 있으면 `publish_post` → `request_indexing`.
3. **반려된 초안 고치기**: `get_approval_status`로 반려 사유를 읽고 `update_draft` → `check_quality` → `request_approval`.
4. **새 초안**: 승인을 기다리는 초안이 없을 때만 쓴다. `get_strategy`, `get_backlog`, `read_record`, `get_git_log`로 글감과 재료를 고르고 `create_draft` → `check_quality`(실패하면 최대 2번 고친다) → `request_approval`. 일요일에는 `get_week_summary`로 주간 보고서를 쓴다(한·영).
5. **마무리**: 그날 한 일을 `notify_human`(info)으로 #일일요약에 보낸다.

사람은 #승인 알림을 보고 Pi에서 `review approve` 또는 `review reject`를 실행한다(4절). 승인한 글은 다음 날 14:00 사이클에서 발행된다. 14:00에 초안이 오면 그날 편할 때 승인하는 흐름이다.

blogops가 강제하는 한도:

| 한도 | 값 | 이유 |
| --- | --- | --- |
| 승인 대기 초안 | 1개 | 사람이 바쁘면 초안이 쌓이지 않고 멈춘다 |
| 발행 | 하루 1편 (KST) | architecture.md 가드레일 |
| 사이클당 툴 호출 | 60회 | `claude -p`에 턴 수 제한 옵션이 없다 (2.1.289 확인) |
| 품질 검사 | 초안당 3번 실패하면 보류 | 보류하면 #긴급으로 알린다 |
| 사이클 실행 시간·메모리 | 30분, `MemoryMax` | systemd가 강제한다 |

## 2. 툴 (Phase 1, 18개)

| 영역 | 툴 | 입력 | 하는 일 | 권한 |
| --- | --- | --- | --- | --- |
| 관측 | `get_system_health` | 없음 | 디스크 여유, CPU 온도, 업타임, 사이트 응답, 마지막 빌드 결과 | read |
| 기획 | `get_strategy` | 없음 | `state/strategy.md` | read |
| 기획 | `get_backlog` | 상태(선택) | `state/backlog.json`의 글감 | read |
| 기획 | `manage_backlog` | 추가·수정, 항목 | 글감 추가, 상태·메모 변경 (삭제 대신 `dropped`와 이유) | write |
| 기획 | `list_posts` | 시리즈(선택) | 발행된 글의 슬러그, 제목, 날짜, 시리즈 | read |
| 기획 | `search_posts` | 검색어 | 제목·본문이 비슷한 기존 글 (중복 확인용) | read |
| 기획 | `read_record` | 경로(없으면 목록) | 허용 목록에 있는 공개 기록만 읽는다: `docs/*.md`, `ops/README.md`, `site/README.md` | read |
| 기획 | `get_git_log` | 레포(ops·site), 기간, 개수 | 커밋 메시지만 (변경 내용 제외) | read |
| 초안 | `create_draft` | 백로그 ID, 슬러그, 제목, 요약, 시리즈, 태그, 본문(ko, en), 출처 | 초안 폴더 생성 | write |
| 초안 | `update_draft` | 초안 ID, 바꿀 내용, 고친 이유 | 초안 수정. 품질·승인 기록은 무효가 된다 | write |
| 초안 | `list_drafts` | 없음 | 초안과 상태 | read |
| 초안 | `check_quality` | 초안 ID | 통과 여부, 문제 목록 (6절) | read |
| 승인 | `request_approval` | 초안 ID | #승인에 요약과 승인·반려 명령을 보낸다 | write |
| 승인 | `get_approval_status` | 초안 ID | 상태(대기·승인·반려), 반려 사유 | read |
| 발행 | `publish_post` | 초안 ID | 5절의 검사와 발행 | gated |
| 발행 | `request_indexing` | URL 목록 | IndexNow 색인 요청 (Bing·네이버) | write |
| 보고 | `get_week_summary` | 주(선택) | 한 주의 발행, 승인·반려와 사유, 품질 검사 결과, 사이클 비용(추정) | read |
| 보고 | `notify_human` | 수준(info·warn·critical), 메시지 | 디스코드 #일일요약·#긴급 | write |

- **승인과 반려는 툴이 아니다.** 사람만 쓰는 `review` 명령이다(4절). Huninn이 자기 글을 승인할 길이 없다.
- **architecture.md의 21개 중 Phase 1에서 만들지 않는 것**: `update_strategy`(전략은 사람이 고치고 Huninn은 주간 보고서에서 제안한다), `get_site_stats`·`get_search_stats`·`get_trends`·실험 3개·`queue_naver_digest`(Phase 2), `unpublish_post`(사람이 직접 한다).
- **새로 생기는 것**: `get_backlog`, `read_record`, `get_git_log`, `list_drafts`, `update_draft`, `get_week_summary`. 이 설계가 확정되면 architecture.md 툴 표에 반영한다.

## 3. 파일

```
state/
├── strategy.md, backlog.json     공개 (git)
├── drafts/<초안ID>/               비공개
│   ├── index.ko.md               Hugo 글 형식 그대로 (front matter + 본문)
│   ├── index.en.md               영어판이 있을 때 (주간 보고서는 필수)
│   └── meta.json                 상태, 품질 검사 기록, 승인 요청 기록, 고친 이력
└── approvals/<초안ID>.json        비공개. 사람의 승인·반려 기록
logs/
├── YYYY-MM-DD.jsonl              비공개. 툴 호출과 결정 (하루 한 파일)
└── cycles.jsonl                  비공개. 사이클별 소요 시간과 비용(추정)
```

- **초안 ID**: `YYYYMMDD-<슬러그>` (예: `20261008-naming`).
- **초안 상태**: `writing` → `ready`(품질 통과) → `awaiting_approval` → `approved` 또는 `rejected` → `published`. 반려되면 고쳐서 다시 `writing`부터. 품질 검사를 3번 실패하면 `held`.
- **해시**: 초안 폴더의 글 파일(`index.*.md`)을 이름 순으로 이어 붙인 SHA-256. 품질 통과와 승인을 모두 이 해시와 함께 기록하고, 발행 직전에 다시 계산해 대조한다.

`state/approvals/20261008-naming.json` 예시:

```json
{
  "draft_id": "20261008-naming",
  "decisions": [
    {"at": "2026-10-08T12:10:00+09:00", "decision": "rejected", "hash": "a3f9…", "reason": "탈락 후보를 고른 이유가 빠졌다"},
    {"at": "2026-10-09T13:02:00+09:00", "decision": "approved", "hash": "7c21…"}
  ]
}
```

## 4. 사람용 명령: `review`

```bash
review list                    # 승인 대기·반려·보류 초안
review show <초안ID>            # 본문 경로, 요약, 품질 검사 결과
review approve <초안ID>         # 지금 해시로 승인을 기록한다
review reject <초안ID> "사유"   # 반려를 기록한다. 사유는 필수
```

- `approve`는 품질 검사를 통과한 해시와 지금 해시가 같을 때만 기록된다. 통과 뒤에 파일이 바뀌었으면 거부한다.
- 승인·반려는 로그에 남긴다. 반려를 "사람 개입"으로 셀지는 집계 방식을 정할 때 함께 정한다.

## 5. 발행 흐름 (`publish_post`)

1. 품질 통과 해시가 지금 해시와 같은지 확인한다.
2. 승인 해시가 지금 해시와 같은지 확인한다. 다르면 거부하고 다시 승인을 요청하게 한다.
3. 오늘(KST) Huninn이 발행한 글이 없는지 확인한다.
4. 초안을 `site/content/posts/<슬러그>/`로 복사하고 `date`를 지금 시각으로 넣는다.
5. Hugo를 임시 폴더에 먼저 빌드하고, 성공하면 실제 `public/`을 빌드한다. 실패하면 복사한 글을 지우고 에러를 돌려준다.
6. 사이트 레포에 커밋하고 push한다. 작성자는 `Huninn`, 메시지는 `content(ai): <제목>`.
7. 공개 URL을 요청해 200과 제목을 확인한다. 확인되지 않으면 발행 실패로 기록하고 #긴급으로 알린다.
8. 초안을 `published`로, 백로그 항목도 `published`로 바꾼다.

IndexNow 키 파일은 사이트 루트에 공개로 둔다(IndexNow가 요구하는 방식이라 비밀값이 아니다).

**Phase 2 주의**: 실제 빌드는 `--cleanDestinationDir`로 `public/`을 비우고 다시 만든다. 상태 띠용 `status.json`을 `public/`에 쓰면 발행할 때마다 지워지므로, Phase 2에서 쓰는 위치를 따로 정한다.

## 6. 품질 검사 (Phase 1)

자동으로 확인할 수 있는 것만 본다. 사실이 맞는지는 사람이 승인할 때 본다.

- **front matter**: `title`, `description`, `series`, `tags`가 있다. `author: human`, `sponsored`, `date`는 없다(`date`는 발행할 때 넣는다).
- **시리즈**: Phase 1은 `ops-log`, `weekly-report`만. 주간 보고서는 영어판도 있어야 한다.
- **분량**: 본문 1,000자 이상 6,000자 이하.
- **출처**: 본문에 숫자가 있으면 `sources`가 1개 이상. 우리 레포를 가리키는 링크는 그 파일이 실제로 있는지 확인한다.
- **금지 내용**: gitleaks(`ops/gitleaks.toml`)로 비밀값, 정규식으로 내부 IP·MAC 주소.
- **중복**: 같은 슬러그가 없고, 기존 글과 제목이 거의 같지 않다.
- **빌드**: 임시 폴더에서 Hugo 빌드가 된다.

## 7. 운영 위치: 작업실과 매장 분리 (2026-10-07 결정)

같은 GitHub 레포 두 개를 Pi 안에 두 번 clone해서, 사람이 쓰는 작업실과 Huninn이 쓰는 매장을 나눈다. GitHub 레포는 지금처럼 두 개다.

| | 운영 레포 (`Hun0305/unattendant`) | 사이트 레포 (`Hun0305/unattendant.dev`) |
| --- | --- | --- |
| 작업실 (사람, 개발 세션) | `~/unattendant` | `~/unattendant/site` |
| 매장 (Huninn) | `~/unattendant-live` | `~/unattendant-live/site` |

**왜**: 한 폴더를 같이 쓰면 (1) Huninn의 push에 사람이 아직 push하지 않은 커밋이 같이 올라가고, (2) 고치는 중인 템플릿으로 Huninn이 사이트를 빌드해 그대로 공개되고, (3) 같은 파일을 동시에 고칠 수 있다. 나누면 실제 사이트에는 GitHub main에 올라간 것만 나간다.

**누가 무엇을 push하나** (양쪽 모두 각 레포의 `main`)

| | 운영 레포 | 사이트 레포 |
| --- | --- | --- |
| 사람 (작업실) | 문서, blogops 코드, ops 설정 | 템플릿, CSS, 고정 페이지 |
| Huninn (매장) | `state/` 변경 | 새 글 (`content/posts/`) |

- **파일 주인**: `state/`와 `site/content/posts/`는 Huninn, 나머지는 사람. 같은 파일을 양쪽에서 고치지 않는다.
- **동기화**: Huninn은 사이클을 시작할 때 두 레포를 `git pull --ff-only`로 받고, 사이트가 바뀌었으면 다시 빌드한다. 사람은 작업실에서 작업을 시작할 때 `git pull`을 먼저 한다.
- **push가 겹치면**: 늦은 쪽이 거절된다. Huninn은 `git pull --rebase` 후 한 번 더 push하고, 그래도 실패하면 #긴급으로 알린다.
- **구분**: deploy key는 레포마다 하나라 양쪽이 같은 키로 push한다. 누가 했는지는 커밋 작성자(`Huninn` / `Hun0305`)로 구분한다.
- **Caddy**: `~/unattendant-live/site/public`을 서빙하도록 경로를 바꾼다.
- **비밀값**: 레포 밖 `~/.config/huninn/huninn.env`(600)로 옮겨, 두 폴더 어디에도 두지 않는다.
- **settings.json**: `claudeMdExcludes`에 `~/unattendant-live`의 `CLAUDE.md`를 더한다.
- **매장 폴더도 pre-commit 훅을 거친다.** Huninn의 커밋도 비밀키 검사를 받는다.

## 8. 코드 구조

```
agent/
├── pyproject.toml        Python 3.13, 의존성은 MCP Python SDK(mcp)
├── blogops/
│   ├── config.py         경로, 한도, 환경변수
│   ├── store.py          초안·승인·백로그 파일, 해시
│   ├── records.py        공개 기록 읽기(허용 목록), git log
│   ├── quality.py        품질 검사
│   ├── publish.py        발행
│   ├── notify.py         디스코드 (봇 REST API, 상주 프로세스 없음)
│   ├── indexnow.py
│   ├── log.py            JSONL 기록, 사이클당 툴 호출 수
│   ├── server.py         MCP 서버. 툴은 위 모듈을 부르기만 한다
│   └── review.py         사람용 review 명령
└── tests/
ops/huninn/
├── prompt.md             하루 사이클 지시 (공개)
├── mcp.json              서버 이름 blogops (settings.json 허용 규칙 mcp__blogops와 맞춘다)
└── run-cycle.sh          claude -p 실행, 비용 기록
ops/systemd/huninn-cycle.service, huninn-cycle.timer
```

가상환경은 `agent/.venv`(git 제외)에 둔다.

## 9. 만드는 순서

1. `store`, `review`와 테스트. 사람 쪽 승인 흐름부터 만든다.
2. `records`, `quality`
3. `publish`. 먼저 임시 사이트 사본으로 시험한다.
4. `notify`, `indexnow`, `log`
5. MCP 서버, `mcp.json`, `run-cycle.sh`, `prompt.md`. 손으로 한 번 돌려 초안과 승인 요청까지 확인한다.
6. 운영 위치 분리(7절)와 타이머
7. Huninn의 첫 글 → 게이트 2 시작

## 10. 결정 사항

1. ~~운영 위치 분리~~ 결정 (2026-10-07): 작업실 `~/unattendant`와 매장 `~/unattendant-live`로 나눈다 (7절)
2. ~~발행 시점~~ 결정 (2026-10-07): 승인한 다음 날 사이클에서 발행한다
3. ~~사이클 시각~~ 결정 (2026-10-07): 매일 14:00(KST). 운영자가 오전에는 깨어 있지 않은 날이 많아서
