# AI 자율운영 블로그 — 진행 상황 (2026-10-06 기준)

설계 문서: https://claude.ai/code/artifact/c5cf2218-acfe-4130-996d-4204c9854189
- 탭 1 "AI 자율운영 블로그 — 아키텍처 & MCP 툴 스펙" (설계)
- 탭 2 "시장 조사" (1~5차 조사 반영, 조사 종료)

## 정해진 방향
- 이름: 블로그 unattendant.dev (2026-10-06 구매 완료, 자동 갱신 켬, 만료 2027-10-06), 에이전트 Huninn (Huginn + Muninn)
  - 태그라인 EN: "unattendant — the attendant who isn't there. A blog run by Huninn, an AI living on a Raspberry Pi."
  - 태그라인 KO: "unattendant — 자리에 없는 당번. 라즈베리파이 위에서 AI 'Huninn'이 혼자 운영하는 블로그."
  - 이름 짓는 과정(탈락 후보: nobodywrites, daysunattended, lefttorun, pilog, unattended.*, araseo, untended.garden 등)은 첫 글감
- 정체성은 메타 컨셉, 검색 유입은 Pi 실측 데이터. 포지셔닝 확정: AI가 직접 실측해 정기 발행 + 운영 지표 상시 공개 + 한국어(영어 병행)
- 언어: 한국어 /, 주간 보고서·실험 글은 /en/ 영어판도. 링크드인 공유는 사람이 직접
- 알림: Pi에서 도는 디스코드 봇(이름 Huninn). #긴급 / #승인 / #일일요약
- 스택: Hugo + git을 Pi에서 서빙(Caddy 8080), Cloudflare Named Tunnel(기존 cloudflared 재사용), Messages API 자체 루프
- 프로젝트 폴더: ~/unattendant/{site, agent, experiments, state, logs, ops}. site/는 공개 레포, 나머지는 비공개 레포
- 하드웨어: Raspberry Pi 4B 4GB 메인. OS는 재설치하지 않고 기존 Raspberry Pi OS 64비트(trixie) 유지
  - TrueETA(키오스크 포함)는 끔. 이 상태에서 SSH만 붙였을 때 메모리 414MB (2026-10-06 실측)
  - 계획: 콘솔 부팅, Samba·PackageKit·Bluetooth 끄기, unattended-upgrades(자동 재부팅 없음), 스왑 종류 확인 후 zram
  - 같은 Pi의 다른 프로젝트 폴더(Pi_Server, TrueETA 등)는 건드리지 않음
- 노트북(i5-8250U + MX150 + 16GB)은 보조 실험 장비

## 현재 단계: Phase 0 (사이트 띄우기)
- [x] Hugo(extended, arm64), Caddy 설치 (Hugo 0.167.0, Caddy 2.11.7 → ~/.local/bin, ops/install-site-tools.sh)
- [x] site/에 다국어 Hugo 뼈대 + "곧 시작" 페이지 (태그라인 포함)
- [x] Caddy로 site/public을 8080에 서빙 (unattendant-caddy.service, 127.0.0.1:8080)
- [x] ~~기존 cloudflared 터널에~~ unattendant.dev → localhost:8080 추가
  - 2026-10-06 확인: 기존은 TrueETA Quick Tunnel뿐이고 Named Tunnel이 없어서 새로 만듦
  - [x] Named Tunnel `unattendant` 생성 (id bd749433-…), DNS CNAME 연결, 임시 실행으로 https 200 확인
  - [x] unattendant-tunnel.service 등록 (sudo)
- [x] 외부(LTE)에서 https://unattendant.dev 접속 확인 (2026-10-06)
- [x] Cloudflare AI 크롤러 허용 확인: Search·Agent·Training 모두 Allow, Bot Preference Sync 끔, AI Labyrinth·Bot fight mode 끔 (2026-10-06)
