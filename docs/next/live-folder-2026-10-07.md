# 매장 폴더(~/unattendant-live) 만들기 보고서 (2026-10-07)

> 임시 문서. 운영자가 읽으려고 남겼다. CLAUDE.md 문서 목록에는 넣지 않았다. 다 읽으면 지우거나, 필요한 내용만 todo.md, ops/README.md, architecture.md로 옮긴다.
>
> 범위: docs/blogops.md 7절 "작업실과 매장 분리" 중 **Huninn이 상주할 폴더를 만드는 데까지**. 다른 세션이 `~/unattendant`에서 작업 중이어서 작업실의 기존 파일은 건드리지 않았다.

## 한 줄 요약

`~/unattendant-live`에 두 레포를 GitHub에서 새로 받아, Huninn이 바로 돌 수 있는 상태까지 만들고 확인했다. **아직 Huninn은 매장에서 돌지 않고, 사이트도 여전히 작업실 빌드가 서빙된다.** 전환하려면 아래 "남은 일"을 해야 한다.

## 알아야 할 것 5가지

1. **이제 폴더가 두 개다.** 사람은 `~/unattendant`(작업실)에서 일하고, Huninn은 `~/unattendant-live`(매장)에서 일한다. 매장은 직접 고치지 않는다. 매장을 바꾸고 싶으면 작업실에서 고쳐 GitHub main에 push하고, 매장이 pull한다.
2. **매장은 GitHub main만 따라간다.** 작업실을 복사하지 않고 GitHub에서 clone했다. 그래서 작업실에서 커밋만 하고 push하지 않은 것, 고치는 중인 파일은 매장에 없다. 2026-10-07 현재 작업실에 push 안 된 커밋 `9b89c05`(문서)가 있는데, 매장에는 없다.
3. **새 비밀값은 `~/.config/huninn/huninn.env`에 넣는다.** 비밀값 파일을 읽는 순서는 `BLOGOPS_ENV_FILE` → `~/.config/huninn/huninn.env` → `<레포>/.env`다. 이 파일이 생겼으니 작업실에서 돌려도 이쪽이 먼저 읽힌다. 지금은 작업실 `.env`와 내용이 같지만, 새 값(예: IndexNow 키)을 작업실 `.env`에만 넣으면 안 보인다.
4. **작업실과 매장은 Claude 설정 폴더를 같이 쓴다.** 둘 다 `~/.config/huninn/claude`(설정, 로그인)와 `~/.config/huninn/work`(실행 폴더)를 쓴다. 겹쳐 돌리지 않는 한 문제없다. 타이머를 켠 뒤 작업실에서 시험 실행할 때는 시각이 겹치지 않게 한다.
5. **Huninn의 커밋 작성자는 이미 `Huninn`이다.** `agent/blogops/publish.py`가 커밋마다 `-c user.name=Huninn -c user.email=huninn@unattendant.dev`를 붙인다. 폴더 설정이 아니라 명령에 붙이므로, 사람이 매장에서 급하게 커밋해도 사람 이름으로 남는다. todo.md의 "Huninn 커밋 작성자" 항목은 코드상 끝났고 체크만 안 됐다.

## 한 일

재현용 스크립트: `ops/setup-live.sh` (작업실에 새로 추가, **커밋 전**). 여러 번 돌려도 된다. sudo 불필요.

| 단계 | 내용 |
| --- | --- |
| clone | `git@github-unattendant-ops:…/unattendant.git` → `~/unattendant-live` (`1755746`), `…/unattendant.dev.git` → `~/unattendant-live/site` (`c086c6f`, 첫 글 포함). 기존 deploy key 그대로 |
| pre-commit 훅 | 두 레포 모두 `core.hooksPath` = `~/unattendant-live/ops/githooks` (매장 자신의 훅과 gitleaks 규칙) |
| Python | `~/unattendant-live/agent/.venv`에 blogops를 editable로 설치. 작업실 가상환경과 같은 패키지 28개, 같은 버전(mcp 2.3.0) |
| 비밀값 | 작업실 `.env`를 `~/.config/huninn/huninn.env`(600)로 **복사**. 키 7개: `CLAUDE_CODE_OAUTH_TOKEN`, `DISCORD_BOT_TOKEN`, `DISCORD_CH_APPROVAL`, `DISCORD_CH_DAILY`, `DISCORD_CH_URGENT`, `DISCORD_OWNER_ID`, `DISCORD_WEBHOOK_URL` |
| 사이트 | `~/unattendant-live/site/public`에 빌드 |

Huninn용 Claude 설정(`~/.config/huninn/claude/settings.json`)은 이미 설치돼 있었고 레포 원본과 같아서 건드리지 않았다.

## 확인한 것

| 확인 | 결과 |
| --- | --- |
| blogops 테스트 69개를 매장 코드로 | 모두 통과 (19초) |
| `~/unattendant-live/ops/huninn/run-cycle.sh --show` | MCP 서버 실행 파일과 `BLOGOPS_ROOT`가 모두 매장을 가리킨다. 모델 `claude-sonnet-5-5`, 실행 폴더 `~/.config/huninn/work` |
| 비밀값 파일 찾기 | 매장 설정으로 `~/.config/huninn/huninn.env`를 찾는다 |
| MCP 서버를 매장 코드로 직접 띄움 | `blogops` 툴 18개. 목록만 받고 호출은 하지 않아 매장에 기록이 남지 않았다 |
| `~/unattendant-live/ops/huninn/review list` | 처리할 초안 없음. 매장은 빈 상태로 시작한다 (작업실의 시험 초안은 따라오지 않는다) |
| 매장 훅으로 `ops/test-pre-commit.sh` | 15개 경우 모두 기대대로 (구독 토큰, 디스코드 토큰, `.env`, 초안 등 차단) |
| 매장 빌드 vs 지금 서빙 중인 작업실 빌드 | 파일 차이 0개. Caddy를 매장으로 바꿔도 사이트는 그대로다 |
| 두 clone의 git 상태 | 변경 0 |
| 디스크 | 매장 폴더 57MB, SD카드 여유 40GB |

## 남은 일 (분리를 끝내려면)

순서대로 하는 것을 추천한다.

1. **`ops/setup-live.sh` 커밋**: 다른 세션의 커밋에 섞이지 않게 따로 `ops: 매장 폴더 설치 스크립트 추가`로 올린다. ops/README.md 구성 표에도 한 줄 넣는다.
2. **`claudeMdExcludes`에 매장 경로 추가**: `ops/huninn/settings.json`에 `/home/hun/unattendant-live/CLAUDE.md`, `/home/hun/unattendant-live/**/CLAUDE.md`를 더하고 `ops/install-huninn-config.sh`로 다시 설치한다. 지금도 실행 폴더가 레포 밖이라 매장의 CLAUDE.md를 읽을 일은 없지만, 두 번째 방어선이다.
3. **Caddy 전환 (sudo, 운영자)**: Caddyfile의 `root`를 `/home/hun/unattendant-live/site/public`으로 바꾸고, `unattendant-caddy.service`가 읽는 Caddyfile 경로도 매장 쪽(`~/unattendant-live/ops/caddy/Caddyfile`)으로 옮긴 뒤 재시작한다. 작업실의 설정 수정이 서버에 바로 반영되지 않게 하려는 것이다. 터널 설정(`ops/cloudflared/config.yml`)도 같은 이유로 매장 쪽을 보게 할지 정한다.
4. **`review` 명령 연결**: `ln -s ~/unattendant-live/ops/huninn/review ~/.local/bin/review`. 그 뒤로 승인·반려는 매장의 초안을 다룬다.
5. **작업실 `.env` 정리**: 작업실에서 시험 실행이 끝나면 지운다. 그 전까지 새 비밀값은 두 파일 모두가 아니라 `huninn.env`에만 넣고, 시험 명령의 `BLOGOPS_ENV_FILE=~/unattendant/.env`를 빼면 된다.
6. **타이머**: 매일 14:00 KST, 매장의 `run-cycle.sh`를 돌린다 (todo.md).
7. **문서 반영**: CLAUDE.md(구조에 매장 폴더), architecture.md(디렉터리 구조), todo.md(운영 폴더 분리, 커밋 작성자 항목 체크), ops/README.md.

## 매장을 다시 만들거나 지울 때

- 다시 만들기: `rm -rf ~/unattendant-live` 후 `~/unattendant/ops/setup-live.sh`. 비밀값 파일은 이미 있으면 그대로 둔다.
- 매장에만 있는 것: `state/`의 초안·승인 기록과 `logs/`는 git에 올라가지 않으므로, Huninn이 돌기 시작한 뒤에 지우면 사라진다. 지우기 전에 백업한다.
