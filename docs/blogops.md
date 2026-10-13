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

사람은 #승인 알림의 [미리보기]로 발행될 모습 그대로 글을 읽고, 버튼으로 승인·반려·접기를 한다(11절). 폰이 아니어도 Pi에서 `review` 명령으로 같은 결정을 할 수 있다(4절). 승인한 글은 다음 날 14:00 사이클에서 발행된다. 14:00에 초안이 오면 그날 편할 때 승인하는 흐름이다. 반려하거나 접으면 14:00을 기다리지 않고 사이클을 바로 한 번 더 돌린다(하루 5회까지, 12절).

blogops가 강제하는 한도:

| 한도 | 값 | 이유 |
| --- | --- | --- |
| 승인 대기 초안 | 1개 | 사람이 바쁘면 초안이 쌓이지 않고 멈춘다 |
| 발행 | 하루 1편 (KST) | architecture.md 가드레일 |
| 사이클당 툴 호출 | 60회 | `claude -p`에 턴 수 제한 옵션이 없다 (2.1.289 확인) |
| 품질 검사 | 초안당 3번 실패하면 보류 | 보류하면 #긴급으로 알린다 |
| 사이클 실행 시간·메모리 | 30분, `MemoryMax` | systemd가 강제한다 |
| 반려·접기 직후 임시 실행 | 하루 5회 (KST) | 반려 → 재작성 → 반려가 되풀이되며 구독 한도를 쓰는 일을 막는다 (12절) |

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
| 승인 | `request_approval` | 초안 ID | 초안 미리보기를 빌드하고, #승인에 요약, 미리보기 링크, 승인·반려·접기 버튼, 명령 안내를 보낸다 (11절). 미리보기를 못 만들어도 승인 요청은 간다 | write |
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
│   ├── *.svg, *.png, *.jpg, *.webp  글에 넣는 그림 (운영자가 이 폴더에 넣는다. 2026-10-12)
│   └── meta.json                 상태, 품질 검사 기록, 승인 요청 기록(디스코드 메시지 위치), 미리보기 토큰, 고친 이력
├── approvals/<초안ID>.json        비공개. 사람의 승인·반려 기록 (결정한 곳 via: cli·discord)
└── previews/<토큰>/               비공개. 승인 대기 초안을 사이트 전체와 함께 빌드한 미리보기 (11절)
logs/
├── YYYY-MM-DD.jsonl              비공개. 툴 호출과 결정 (하루 한 파일)
├── cycles.jsonl                  비공개. 사이클별 소요 시간과 비용(추정)
└── .cycle-request                반려·접기 직후 사이클을 돌려 달라는 요청 (12절). 서비스가 시작하며 지운다
```

- **초안 ID**: `YYYYMMDD-<슬러그>` (예: `20261008-naming`).
- **초안 상태**: `writing` → `ready`(품질 통과) → `awaiting_approval` → `approved` 또는 `rejected` → `published`. 반려되면 고쳐서 다시 `writing`부터. 품질 검사를 3번 실패하면 `held`.
- **해시**: 초안 폴더의 글 파일(`index.*.md`)과 그림 파일을 이름 순으로 이어 붙인 SHA-256. 그림이 없는 초안의 해시는 그림 기능이 생기기 전과 같다. 품질 통과와 승인을 모두 이 해시와 함께 기록하고, 발행 직전에 다시 계산해 대조한다.

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
review show <초안ID>            # 본문 경로, 요약, 품질 검사 결과, 미리보기 주소
review preview <초안ID>         # 승인 대기 초안의 미리보기를 (없으면) 만들고 주소를 보인다
review approve <초안ID>         # 지금 해시로 승인을 기록한다
review reject <초안ID> "사유"   # 반려를 기록한다. 사유는 필수
review reject <초안ID> "사유" --drop   # 접기: 반려 + 보류 + 글감 blocked (이 주제는 그만)
```

- `approve`는 품질 검사를 통과한 해시와 지금 해시가 같을 때만 기록된다. 통과 뒤에 파일이 바뀌었으면 거부한다.
- 반려만 하면 Huninn이 다음 사이클에 같은 글을 고친다. 글감 자체를 그만두려면 `--drop`(디스코드의 [접기])을 쓴다. 초안은 `held`가 되어 더 고치지 않고, 백로그 글감은 `blocked`로 바뀐다.
- 승인·반려는 로그에 남긴다. 반려를 "사람 개입"으로 셀지는 집계 방식을 정할 때 함께 정한다.

## 5. 발행 흐름 (`publish_post`)

1. 품질 통과 해시가 지금 해시와 같은지 확인한다.
2. 승인 해시가 지금 해시와 같은지 확인한다. 다르면 거부하고 다시 승인을 요청하게 한다.
3. 오늘(KST) Huninn이 발행한 글이 없는지 확인한다.
4. 초안을 `site/content/posts/<슬러그>/`로 복사하고 `date`를 지금 시각으로 넣는다. 그림 파일도 같은 폴더로 복사한다.
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
- **그림** (2026-10-12): 본문에 `{{< fig src="…" caption="…" >}}`를 쓰면 같은 이름의 파일이 초안 폴더에 있어야 하고, 본문에서 쓰지 않는 그림 파일은 없어야 한다. `caption`(누가 만들었는지, 남의 그림이면 출처와 라이선스)은 필수, SVG가 아닌 그림은 `alt`도 필수다. 파일 하나는 200KB 이하. SVG는 본문에 그대로 들어가므로 `<script>`, `<foreignObject>`, `on…=` 속성, `javascript:`, 외부 주소 참조가 있으면 실패한다. 그림 파일의 해시도 승인에 포함돼서 승인 뒤 파일을 바꾸면 발행이 거부된다. Huninn은 그림을 만들거나 받을 수 없으므로 지금은 운영자가 파일을 넣고 Huninn이 아니라 운영자가 본문에 `fig`를 쓴다(전략 "시각자료")

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
├── pyproject.toml        Python 3.13, 의존성은 MCP Python SDK(mcp), 봇은 선택(`.[bot]`: discord.py)
├── blogops/
│   ├── config.py         경로, 한도, 환경변수
│   ├── store.py          초안·승인·백로그 파일, 해시
│   ├── records.py        공개 기록 읽기(허용 목록), git log
│   ├── quality.py        품질 검사
│   ├── publish.py        발행
│   ├── notify.py         디스코드 메시지 (봇 REST API). #승인 메시지에 미리보기 링크와 버튼을 붙이고, 결정이 나면 그 메시지를 결과로 고친다
│   ├── preview.py        승인 대기 초안의 미리보기 빌드 (11절)
│   ├── buttons.py        #승인 버튼 형식 (custom_id, components). discord.py 없이 쓴다
│   ├── decisions.py      승인·반려·접기. review 명령과 봇이 같이 쓴다
│   ├── ondemand.py       반려·접기 직후 사이클을 바로 돌려 달라는 요청 (12절)
│   ├── bot.py            디스코드 봇(상주). 버튼 클릭을 decisions에 넘긴다. discord.py 필요
│   ├── indexnow.py
│   ├── log.py            JSONL 기록, 사이클당 툴 호출 수
│   ├── server.py         MCP 서버. 툴은 위 모듈을 부르기만 한다
│   └── review.py         사람용 review 명령
└── tests/
ops/huninn/
├── prompt.md             하루 사이클 지시 (공개)
├── mcp.json              서버 이름 blogops (settings.json 허용 규칙 mcp__blogops와 맞춘다)
└── run-cycle.sh          claude -p 실행, 비용 기록
ops/systemd/huninn-cycle.service, huninn-cycle.timer, huninn-cycle-now.path, huninn-bot.service
ops/caddy/Caddyfile   :8080 공개 사이트, :8081 미리보기
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
8. 폰에서 읽고 승인하기: 미리보기 페이지와 디스코드 버튼 (11절)
9. 반려·접기 직후 사이클을 바로 돌리기 (12절)

## 10. 결정 사항

1. ~~운영 위치 분리~~ 결정 (2026-10-07): 작업실 `~/unattendant`와 매장 `~/unattendant-live`로 나눈다 (7절)
2. ~~발행 시점~~ 결정 (2026-10-07): 승인한 다음 날 사이클에서 발행한다
3. ~~사이클 시각~~ 결정 (2026-10-07): 매일 14:00(KST). 운영자가 오전에는 깨어 있지 않은 날이 많아서

## 11. 폰에서 읽고 승인하기 (2026-10-13)

승인은 Pi의 `review` 명령으로만 할 수 있었다. 운영자가 폰에서 글을 읽고 바로 승인·반려할 수 있게, #승인 메시지에 **미리보기 링크**와 **버튼**을 붙인다. 두 부분이다: 읽는 쪽(미리보기 페이지)과 결정하는 쪽(디스코드 봇).

```
request_approval ─▶ Hugo로 초안을 포함한 사이트 전체를 빌드 ─▶ state/previews/<토큰>/
                 ─▶ #승인 메시지: [미리보기] [영어판] [승인] [반려] [접기]
폰 ─▶ https://preview.unattendant.dev/<토큰>/posts/<슬러그>/
        └ Cloudflare 터널 ─▶ Caddy :8081 (읽기 전용 file_server)
폰 ─▶ 버튼 ─▶ 디스코드 ─▶ huninn-bot.service ─▶ decisions.py ─▶ state/approvals/
```

### 미리보기 페이지 (`preview.py`)

- **실제 사이트 그대로**: 초안을 `content/posts/<슬러그>/`에 넣고 사이트 전체를 빌드한다. 글꼴, 다크 모드, 그림, 메뉴 이동이 발행된 모습과 같다. 한국어와 영어판을 둘 다 굽는다. 빌드는 1초 안팎이다. `--minify`는 쓰지 않는다(HTML minify가 `<body>`를 지워 "미승인 초안" 띠를 넣을 수 없다). 띠는 초안 페이지에만 들어간다.
- **접근 통제는 토큰 주소**: 폴더 이름이 `secrets.token_hex(20)`(160비트)이다. 주소를 아는 사람만 읽는다. 토큰은 `meta.json`(비공개)에 두므로 `.env`에 새 비밀값이 생기지 않는다. 로그인은 없다. 더 막고 싶으면 Cloudflare Access를 `preview.unattendant.dev`에 겹치면 된다(코드 변경 없음).
- **지금 버전만**: 승인 대기 초안의 지금 버전에만 미리보기가 있다. 내용이 바뀌어 해시가 달라지면 새 토큰이 나오고 옛 폴더는 지운다. 결정(승인·반려·접기)이 나면 바로 지운다. 링크가 보여 주는 내용과 승인 버튼이 승인할 내용은 늘 같은 버전이다.
- **Caddy `:8081`**: 폴더 목록을 보여 주지 않고(`/`는 404), 점으로 시작하는 이름과 상위 경로는 내주지 않는다. 읽기 전용이다(POST 405). 모든 응답에 `X-Robots-Tag: noindex`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`를 붙이고 `/robots.txt`는 전체 차단이다. 사이트 CSS가 `/fonts/…`를, 상태 띠가 `/status.json`을 절대 경로로 부르므로 이 둘만 공개 사이트 폴더에서 그대로 내준다.
- **비공개 폴더**: `state/previews/`는 `.gitignore`와 pre-commit 훅이 막는다. `sync.commit_state`가 `git add -- state`를 하므로 이 보호가 없으면 미완성 글이 공개 레포에 올라간다.
- **Huninn에게는 주소를 돌려주지 않는다**: 토큰이 든 주소는 열쇠라서 디스코드 #승인으로만 간다. `request_approval`은 `preview: true/false`만 돌려준다.
- **실패해도 막지 않는다**: 빌드가 실패하면 승인 요청은 그대로 가고, 메시지에 미리보기를 못 만들었다는 말과 `review preview` 안내가 붙는다.

### 디스코드 버튼 (`bot.py`, `buttons.py`, `decisions.py`)

| 버튼 | 누르면 |
| --- | --- |
| 미리보기, 영어판 | 링크 버튼. 브라우저로 미리보기 페이지가 열린다 |
| 승인 | 나만 보이는 확인 메시지 [승인 확정] [취소]. 확정하면 승인이 기록된다 |
| 반려 | 사유 입력창. 제출하면 반려가 기록되고, Huninn이 다음 사이클에 사유를 읽고 고친다 |
| 접기 | 사유 입력창. 제출하면 반려 + 초안 보류 + 글감 `blocked` (이 주제는 그만) |

- **게이트웨이 방식**: 봇이 디스코드로 먼저 연결을 열어서 포트도, 공개 주소도 필요 없다. 권한 인텐트는 쓰지 않는다(`Intents(guilds=True)`뿐). 버튼 `custom_id`가 `bo:<동작>:<초안ID>:<해시12자>`라 봇이 다시 떠도 이전 메시지의 버튼이 그대로 동작한다.
- **사칭 방지**: 모든 클릭, 확인, 사유 제출에서 `DISCORD_OWNER_ID`와 클릭한 사람의 ID를 대조한다. 다르면 거부하고 `approval_denied`를 기록한다.
- **해시 대조**: 버튼에 든 해시가 초안의 지금 해시와 다르면 거부한다. 확인 창을 오래 두거나 오래된 메시지의 버튼을 눌러도 새 내용을 승인하지 못한다. 기록 단계(`Store.record_decision(expect_hash=…)`)에서도 잠금 안에서 한 번 더 비교한다.
- **같은 기록**: 승인·반려는 `review` 명령과 같은 `decisions.py`를 거친다. 어디서 했는지만 `via`(cli·discord)로 남는다.
- **메시지 정리**: 결정이 나면 #승인 메시지를 결과 한 덩이("승인함 — 제목 · 시각")로 고치고 버튼과 링크를 걷어낸다. `review` 명령으로 결정해도 같다(승인 요청을 보낸 메시지 위치를 `meta.json`에 적어 둔다). 정리가 실패해도 결정은 이미 기록된 것이라 경고만 한다.
- **봇이 멈추면**: 버튼이 "상호작용 실패"가 될 뿐이다. 알림은 계속 가고 메시지의 `review` 명령으로 승인할 수 있다. systemd가 봇을 다시 띄운다.
- **서비스** (`huninn-bot.service`): 매장의 `blogops.bot`, `MemoryMax=200M`, 쓰기는 `state/`와 `logs/`만. 봇은 글을 쓰거나 발행하지 않고 claude 토큰도 읽지 않는다. 설치는 [ops/README.md](../ops/README.md) "Huninn 봇".

### 남은 것

- 반려·접기 직후 바로 다시 쓰기는 12절에서 한다.
- 봇이 죽었는지를 `get_system_health`가 알리지는 않는다.
- 미리보기 주소가 새는 것이 걱정되면 Cloudflare Access를 겹친다. 초안은 승인되면 어차피 공개될 글이라 지금은 토큰 주소로 충분하다고 판단했다(2026-10-13 운영자 결정).

## 12. 반려·접기 직후 바로 쓰기 (2026-10-13)

반려나 접기를 해도 Huninn은 다음 14:00 사이클(최대 하루 뒤)에야 움직였다. 운영자가 정한 대로(2026-10-13) 반려와 접기는 사이클을 바로 한 번 더 돌린다.

| 결정 | 바로 도는 사이클이 하는 일 |
| --- | --- |
| 반려 | 같은 초안을 사유대로 고쳐 품질 검사를 거쳐 다시 승인을 요청한다 (프롬프트 3번) |
| 접기 | 접은 글감을 빼고 다른 글감으로 새 초안을 쓴다 (프롬프트 4번) |
| 승인 | **돌리지 않는다.** 승인한 글은 다음 14:00 사이클이 발행한다 |

```
[반려]·[접기] 또는 review reject ─▶ decisions.reject: 기록 · 보류 · 글감 blocked를 다 바꾼 뒤
                                  ─▶ ondemand.request: logs/.cycle-request 파일 하나를 쓴다
                                  ─▶ huninn-cycle-now.path가 파일을 보고 huninn-cycle.service를 시작한다
                                  ─▶ 서비스가 시작할 때 요청 파일을 지운다 (ExecStartPre) ─▶ 평소 사이클
```

- **권한**: 봇과 `review` 명령은 파일 하나를 쓸 뿐이다. 서비스를 시작하는 권한(polkit)을 주지 않는다. 사이클을 시작하는 쪽은 systemd path 유닛이다.
- **상한 하루 5회**(KST, `Config.ondemand_daily_limit`): 받아들인 요청을 `logs/YYYY-MM-DD.jsonl`의 `cycle_requested`(granted)로 센다. 5회를 넘으면 요청하지 않고 "오늘 임시 실행 5회를 다 썼다. 다음 14:00 사이클에서 처리한다"고 알린다. 반려 → 재작성 → 반려가 되풀이돼도 구독 한도를 하루 5번 이상 쓰지 않는다. 14:00 정규 사이클은 이 상한과 별개다.
- **유닛이 없으면 약속하지 않는다**: `systemctl show huninn-cycle-now.path`로 유닛이 켜져 있고 지켜보는 파일이 이 설정의 요청 파일과 같은지 본다. 아니면(유닛 설치 전, 작업실에서 시험할 때) 요청 파일을 만들지 않고 "다음 14:00 사이클에서"라고 안내한다. 그래서 코드를 먼저 배포하고 유닛을 나중에 설치해도 안내가 거짓이 되지 않는다.
- **순서**: 기록, 초안 보류, 글감 `blocked`를 모두 바꾼 뒤에 요청한다(테스트로 고정). 사이클이 곧바로 시작해도 접은 글감을 다시 고르지 않는다.
- **겹침**: 요청 하나에 한 번만 돈다. 실행 중에 새 요청이 오면 끝난 뒤 한 번 더 돈다. 그 사이 14:00 타이머가 먼저 돌아도 그 실행이 요청 파일을 지우고 처리한다. 연달아 와도 한 번이다. 사용자 매니저의 임시 유닛으로 확인했다(요청 1번=1번 실행, 실행 중 요청=끝난 뒤 1번 더, 3번 연속=1번, 실제 `ondemand.request`의 파일 쓰기에도 반응).
- **고장 방지**: 요청 파일은 서비스의 `ExecStartPre`와 `cycle.py`가 둘 다 시작할 때 지운다(유닛을 일부만 설치해도 같은 요청으로 계속 돌지 않게). path 유닛에도 `TriggerLimitBurst=8`/1시간을 둬서 그래도 지워지지 않는 고장이 나면 멈춘다.
- **안내**: 디스코드 응답, #승인의 결과 메시지, `review` 출력이 같은 문장(`decisions.next_step`)을 쓴다. 예: "사이클을 바로 돌린다. 1~2분 안에 Huninn이 사유를 읽고 고친 뒤, 품질 검사를 거쳐 다시 승인을 요청한다 (임시 실행 2/5회)."
- **알림**: 새 승인 요청이 오면 그 즉시 멘션이 간다. 밤에도 울린다.
- **프롬프트**: "사이클은 매일 14:00에 한 번 돌고, 운영자가 반려하거나 접으면 바로 한 번 더 돈다(하루 5회까지)"를 `ops/huninn/prompt.md`에 더했다. 순서는 그대로다.
- **알아 둘 것**: 접기는 `state/backlog.json`을 고치므로(미커밋) 바로 도는 사이클의 `git pull --ff-only`가 그 파일이 겹치는 커밋에는 막힌다. 평소에는 사이클 끝의 state 커밋이 정리한다. 설치는 [ops/README.md](../ops/README.md) "반려·접기 직후 바로 쓰기".
