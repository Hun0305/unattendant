# A. todo 체크 상태가 실제와 다른 것
Huninn 커밋 작성자 (112줄): 이미 publish.py에 들어 있어요(Huninn / huninn@unattendant.dev). 다만 메시지와 작성자를 서로 대조하는 훅은 없어요(B4).
승인 흐름 (103줄): review 명령, 해시 대조, #승인 알림이 다 있고, 03:47 시험에서 Huninn이 승인 요청까지 했어요. 남은 건 실제 환경에서 승인하고 다음 날 발행되는 것을 한 번 보는 일인데, 게이트 2의 첫 글에서 자연스럽게 확인돼요.
blogops 상위 항목 (92줄): 하위 1~5단계는 다 체크돼 있어요. 6단계와 7단계는 별도 항목(108·109줄, 게이트 2)이라 상위 항목도 체크해도 돼요.
운영 폴더 분리 (108줄): 다른 세션에서 진행 중이에요. ~/unattendant-live의 clone, 훅, 가상환경, huninn.env(600), 빌드까지 됐어요. 그 스크립트(ops/setup-live.sh)는 아직 커밋 전이에요. Caddy는 아직 작업실의 site/public을 서빙하고 있어요.

# B. todo에 없지만 매일 돌리기 전에 필요한 것
사이클 시작 때 동기화하는 코드가 없어요. 설계(blogops.md 7절)에는 두 레포를 git pull --ff-only로 받고, 사이트가 바뀌었으면 다시 빌드한다고 돼 있어요. 이게 없으면 사람이 push한 템플릿이나 문서가 매장에 들어가지 않아요.
state/ 변경을 커밋하고 push하는 코드가 없고, 파일 주인 규칙도 서로 맞지 않아요. 7절은 state/를 Huninn의 파일이라고 하는데, 2절은 Phase 1에서 전략 문서(state/strategy.md)를 사람이 고친다고 해요. 매장 분리를 끝내기 전에 정해야 해요.
구독 한도에 걸리면 그날은 그대로 끝나요. 01:55 첫 시험이 실제로 이걸로 실패했어요. 지금은 #긴급 알림만 보내고 다음 날까지 다시 돌지 않아요. 14:00 전후에는 개발 세션을 쓰지 않을지, 실패하면 몇 시간 뒤에 한 번 더 돌게 할지 정해야 해요.
커밋 메시지와 작성자를 대조하는 훅이 없어요. CLAUDE.md 규칙에는 있는데, ops/githooks에는 pre-commit(gitleaks)만 있어요. commit-msg 훅으로 content(ai) ⇔ 작성자 Huninn을 검사하면 돼요.
비공개 기록의 백업이 없어요. state/drafts, state/approvals(승인 증거), logs/는 git 밖이라 Pi에만 있어요. architecture.md의 백업 표에는 있는데 todo에는 없어요. Phase 2로 미루더라도 항목은 있어야 해요.
문서가 실제와 달라요 (보고서의 "설계와 다른 점"): architecture.md 툴 표에 새 툴 6개가 빠져 있고, blogops.md 8절의 코드 구조도 실제와 달라요(모듈 18개, cycle.py).

# C. 사람이 해야 하는 것
첫 글 색인 (기한 10-13): 사이트 쪽에는 막는 게 없어요. 200 응답, robots 메타 없음, canonical·hreflang 정상, 사이트맵에 포함돼 있고, Googlebot UA로 요청해도 200이에요. 남은 건 Search Console의 URL 검사와 색인 요청, 네이버 수집 요청이에요.
업타임 모니터 (78줄)
디스코드 봇 이름: API로 확인해 보니 아직 Hunnin이에요. 알림이 이 이름으로 가요.
친구 피드백 반영: 정할 것 8개가 docs/toberead/draft-feedback-2026-10-07.md에 정리돼 있어요(118·122줄).
push 안 한 커밋 2개 (9b89c05, cd14e1d): 매장은 GitHub에서 받기 때문에, push하기 전에는 Huninn이 read_record로 읽는 문서가 한 단계 옛 버전이에요.
D. 작은 것
CLAUDE.md "환경"에 "기존 터널에 호스트 이름을 추가"라고 돼 있는데, 실제로는 전용 Named Tunnel을 쓰고 있어요.
indexnow.md가 docs/toberead/로 옮겨져서, 제가 CLAUDE.md와 todo에 건 링크가 깨졌어요.
hreflang x-default가 모든 글에서 홈을 가리켜요. 보통은 같은 글의 한국어판을 가리켜요. 급하지 않아요.
작업실에 시험 초안 20261007-gitleaks-on-pi가 승인 대기로 남아 있어요. 작업실에서 다시 시험을 돌리면 "승인 대기 1개" 한도에 막혀요.
추천 순서
state/의 주인과 push 방식 정하기 (B2). 매장 분리를 끝내기 전에요.
feat/ 브랜치에서 B1~B4 코드 작업
매장 분리 마무리(Caddy 경로 변경, sudo)와 타이머
Huninn 첫 사이클 → 게이트 2 시작
C는 그사이에 병행하면 돼요. todo에 B 항목들을 추가하고 A의 체크를 정리할까요? CLAUDE.md 규칙대로, 문서를 고치기 전에 먼저 여쭤봐요.



