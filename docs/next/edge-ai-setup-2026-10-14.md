# 엣지 AI 실험 시작: 설계와 환경 준비 보고서 (2026-10-14)

> 임시 문서. 운영자가 읽으려고 남겼다. CLAUDE.md 문서 목록에는 넣지 않았다. 다 읽으면 지우거나, 필요한 내용만 docs/experiments.md, todo.md, ops/README.md로 옮긴다.
>
> 범위: 2026-10-14 새벽 개발 세션 하나에서 한 일. 엣지 AI 실험의 설계(docs/experiments.md 초안), 첫 측정을 돌릴 수 있는 데까지의 환경 준비, 그 과정에서 정한 인바운드 가드(방화벽)다. **모든 변경은 커밋 전이다.**

## 한 줄 요약

설계 문서를 쓰고 llama.cpp 빌드, 모델 8종, 측정 러너(속도 `llm-bench`, 품질 `llm-tasks`), 과제 세트 초안까지 준비했다. 첫 측정(속도 `round1-bench`, 이어서 품질 러너 검증 `trial-tasks`)은 예약만 돼 있고 **아직 모델을 한 번도 돌리지 않았다.** VS Code 서버가 떠 있는 동안에는 시작하지 않는다. 같은 세션에서 인바운드 가드를 만들어 운영자가 적용했다.

## 알아야 할 것 6가지

1. **아직 아무것도 재지 않았다.** 세션 내내 VS Code 원격 연결 중이어서 모델을 실행하지 않았다(CLAUDE.md 규칙). 러너 시험은 가짜 llama-bench·llama-server로 했다. 그날 05:30 전에 VS Code 서버가 꺼지면 측정이 시작되고, 아니면 매일 02:00 타이머가 이어서 돈다.
2. **모든 변경이 커밋 전이다.** 커밋할 때 문서(main)와 실험 코드(feat/ 브랜치, PR)를 나눈다. 같은 시각 다른 세션이 커밋한 `e6552ff`(문서 경로 정리)가 있고, `docs/next/live-folder-2026-10-07.md`와 `docs/next/phase1_review.md`의 삭제는 이 세션이 한 것이 아니다. 섞어 커밋하지 않는다.
3. **실험은 사용자 매니저의 임시 유닛으로 돈다.** sudo 없이 시작하려고 시스템 유닛 대신 `systemd-run --user`를 썼다. 재부팅하면 예약이 사라진다. 사용자 매니저는 tty1 자동 로그인 세션이 붙잡고 있다.
4. **러너 기록은 `logs/experiments.jsonl`에 남는다.** 사용자 저널 파일이 없어서 `journalctl --user`로는 안 보이고, `journalctl --user-unit=<유닛>`으로는 보인다.
5. **llama.cpp는 이제 정식 릴리스(`v0.x`)와 매일 나오는 프리릴리스(`bNNNNN`)가 따로 있다.** 버전 고정과 월 1회 업그레이드는 정식 릴리스를 기준으로 한다.
6. **보안 점검에서 나온 것은 이 문서에 적지 않았다.** 공개 레포라서다. 내용은 대화로 전달했다. 조치는 정해서 적용했다: 인바운드 가드(SSH·FTP·MQTT·rpcbind를 집 안과 Tailscale에서만 받는다, 2026-10-14 02:55 운영자 적용). 설명은 ops/README.md "인바운드 가드 (sudo)".

## 한 일

| 영역 | 내용 | 위치 |
| --- | --- | --- |
| 설계 | 엣지 AI 실험 설계 초안: 모델 선정 기준과 1회차 8종, 측정 지표와 고정 설정, 과제 세트, 측정 오염을 막는 규칙, 결과 형식, 템플릿, 비전 트랙, 정할 것 8개 | `docs/experiments.md` |
| 런타임 | llama.cpp `v0.6.0`(2026-10-05, 커밋 d812350, ggml 0.26.0)을 얕게 clone해 빌드. Release, 테스트·예제 끔. `llama-bench`, `llama-server`, `llama-cli`, `llama-perplexity`. 사용자 범위(`MemoryMax=1536M`)에서 `-j2`, `nice 10`. 빌드 설정과 CPU 감지 결과는 `build-configure.log` | `~/opt/llama.cpp/v0.6.0` (323MB) |
| 모델 | 1회차 8종 Q4_K_M을 받고 sha256 대조. 저장소 커밋, 파일 해시, GGUF 구조를 고정. 모두 로그인 없이 받는 저장소라 Hugging Face 토큰을 Pi에 두지 않았다 | `~/models/gguf` (6.6GB), `experiments/models.toml` |
| 러너 | 공통 로거(1초), 무효 판정, `llm-bench`(속도), `llm-tasks`(품질: llama-server 스트리밍으로 TTFT·서버 timings, 콜드 로드 3회, 결정성 확인), 밤 실행(`night.py`, 계획 여러 개), 모델 받기(`fetch_models.py`), 시험 25개 | `experiments/runner/` |
| 템플릿·계획 | `llm-bench` v1: 허용 범위(양자화 4종, 스레드 1~4, 시험 3종)와 고정값(`--load-mode none`). `llm-tasks` v1: 서버 슬롯 1개, 프롬프트 캐시·RAM 캐시(기본 8GB)·문맥 체크포인트·메모리 자동 맞춤 끔, 그리디. 계획 `round1-bench`(속도 9개 작업), `trial-tasks`(기준 모델로 품질 러너 검증), `round1-tasks`(8종 품질, 검수 뒤에 넣는다) | `experiments/templates/`, `experiments/plans/` |
| 과제 세트 | `llm-tasks-v1` 초안(`status = "draft"`): 한국어 100문항(명령→JSON 30, 의도 분류 30, 정보 추출 20, 짧은 답 20), 지시문과 예시 2개, 규칙 기반 채점기, T1 JSON 스키마, 검수 안내 | `experiments/promptsets/llm-tasks-v1/` |
| 예약 | `exp-night-20261014`(그날 05:30까지 시작 조건을 기다림, `round1-bench`만), `exp-night.timer`(매일 02:00, `round1-bench` 다음 `trial-tasks`) | 사용자 매니저 |
| 인바운드 가드 | nftables 표 하나(`inet unattendant_guard`): SSH·FTP·MQTT·rpcbind를 로컬, Tailscale, 링크 로컬 IPv6, 같은 IPv4 대역에서만 받는다. 적용할 때 10분 뒤 자동 되돌리기, 확인 뒤 확정. 부팅 유닛. 가상 네트워크 시험 | `ops/install-firewall.sh`, `ops/firewall/`, `ops/systemd/unattendant-firewall.service`, `ops/test-firewall.sh` |
| 문서 | experiments.md 7절(규칙)·9절(폴더)·13절(진행), todo.md(실험 러너 절, 인바운드 가드 절), CLAUDE.md 문서 목록, `experiments/README.md`, `ops/README.md` "인바운드 가드 (sudo)" | |

## 러너가 지키는 것

| 상황 | 동작 |
| --- | --- |
| 메모리 상한 없이 실행 | 시작하지 않는다 (CLAUDE.md: 실험은 systemd 서비스 + MemoryMax로만) |
| 다른 실험이 도는 중 | 시작하지 않는다 (`logs/exp-run.lock`) |
| VS Code 서버 프로세스, Huninn 사이클, MemAvailable < 2.8GB, 1분 부하 ≥ 0.5 | 시작하지 않고 10분 뒤 다시 본다. 05:30이 지나면 다음 밤으로 미룬다 |
| 시작 온도 > 50°C | 최대 10분 식힌다. 그래도 높으면 재되 무효로 남긴다 |
| 측정 중 VS Code 서버가 뜸 | 작업을 멈추고, 조건이 다시 맞으면 그 작업을 처음부터 돈다 |
| 측정 중 Huninn 사이클 시작 | 그 측정만 멈추고 사이클이 끝난 뒤 다시 잰다 (시도 횟수로 세지 않는다) |
| 측정 중 80°C | 멈추고 다시 재지 않는다 (architecture.md 과열 가드레일) |
| 스로틀링·저전압 비트, 스왑 1MB 초과, 다른 프로세스 CPU 평균 5% 초과 | 무효. 한 번 다시 재고, 또 무효면 사유와 함께 남긴다 |
| 메모리 상한 초과(OOM) | 실패로 남기고 다시 재지 않는다 |
| llama-bench 한 번이 30분을 넘김 | 멈춘다 |
| 모델별 첫 측정 | 측정 전에 모델 파일을 페이지 캐시에서 비우고 한 번 읽는다. 디스크 I/O가 측정에 섞이지 않게 하고, 그 시간을 콜드 로드(SD 읽기 속도) 값으로 남긴다 |

실행 유닛은 `MemoryMax=2500M`, `MemorySwapMax=0`, `OOMScoreAdjust=500`, `Nice=5`, `RuntimeMaxSec=4h`다. 메모리가 모자라면 실험이 먼저 죽는다.

## 확인한 것

| 확인 | 결과 |
| --- | --- |
| CPU 명령어 확장 | `/proc/cpuinfo`: `fp asimd evtstrm crc32 cpuid`. dotprod·i8mm 없음 |
| llama.cpp ARM 최적화 경로 | 소스(`ggml-cpu/repack.cpp`): 가중치 재배치는 dotprod·i8mm·SVE가 있어야 켜진다. 빌드 설정도 `-mcpu=cortex-a72+crc+nodotprod+noi8mm+nosve+nosme`를 골랐다 |
| `--load-mode none` | `llama.h`: "no special loading mode", 곧 mmap·mlock 없이 메모리로 읽는다. 설계의 "mmap 끔"과 맞다 |
| upstream 지원 | 8종의 GGUF 구조(`llama`, `gemma3`, `qwen35`, `lfm2`, `granitehybrid`, `exaone4`)가 모두 `llama-arch.cpp`에 있다. Kanana-2 1.3B(`kanana2tiny`)는 없다 |
| 생각 모드 기본값 | Qwen3.5 0.8B·2B, EXAONE 4.0 1.2B는 기본 꺼짐(모델 카드). 나머지는 생각 모드가 없다 |
| 모델 받기 | 약 20~25MB/s. 중간에 끊은 Llama(331MB에서 끊음)를 이어 받은 뒤 sha256이 맞았다 |
| 빌드 | exit 0. 빌드 중 두 번 본 메모리 최댓값 약 1.0GB(상한 1.5GB). 바이너리 4개 모두 `0.6.0-dev (commit d812350)` |
| 러너 시험 | 25개 통과. 가짜 llama-bench·llama-server라 모델을 실행하지 않는다. 가짜 서버로 100문항을 끝까지 돌려 만점, 결정성 10/10, 요청마다 그리디·캐시 끔·생각 모드 끔, JSON 제약은 T1에만 걸리는 것을 확인 |
| llama-server 옵션 | 쓸 옵션을 없는 모델 파일로 넘겨 옵션 해석이 모두 통과하고 모델 불러오기 단계에서 멈추는 것을 확인(모델은 돌리지 않음) |
| 인바운드 가드 | 가상 네트워크 시험 20건 통과(집 안 열림, 인터넷 쪽 막힘, 다른 포트 그대로, Tailscale·링크 로컬 열림). 운영자 적용 뒤 SSH 인증 실패 기록이 멈췄고 성공한 로그인은 집 안과 Tailscale뿐 |
| 무효 판정 실제 동작 | 빌드가 2코어를 쓰는 동안 가짜 측정이 "다른 프로세스 CPU 평균 약 51%"로 무효가 되고, 한 번 다시 잰 뒤 무효로 남았다 |
| 과제 세트 채점기 | 정답을 그대로 넣으면 4과제 모두 만점 |
| gitleaks | 새 파일을 `ops/gitleaks.toml` 규칙으로 검사해 0건 |
| 예약 | `exp-night-20261014`가 위 설정으로 대기 중. 02:15 기록: VS Code 서버 프로세스 18개, MemAvailable 1378MB, 1분 부하 2.6이라 기다림. 다음 정기 실행 2026-10-15 02:00(두 계획) |

## 보는 법

```bash
tail -f logs/experiments.jsonl                        # 시작·대기·측정·무효 사유
systemctl --user list-timers exp-night.timer          # 다음 실행 시각
cat logs/exp-plans/round1-bench.json                  # 계획의 작업별 상태 (첫 작업이 돈 뒤 생긴다)
column -s, -t < experiments/results/llm-bench/summary.csv   # 속도 결과 한 줄 요약
column -s, -t < experiments/results/llm-tasks/summary.csv   # 품질 결과 (과제별 한 줄)
sudo ops/install-firewall.sh status                   # 인바운드 가드: 막은 횟수, 같은 대역에서 접속한 주소
systemctl --user stop exp-night-20261014.service exp-night.timer   # 예약 취소
```

그날 밤에 바로 돌리려면 VS Code 연결을 끊고 명령 팔레트의 "Remote-SSH: Kill VS Code Server on Host"로 서버까지 끈다. 그 VS Code에서 돌던 Claude 세션도 같이 끝난다.

## 정할 것 (운영자)

1. ~~보안 조치~~: 인바운드 가드로 정해 2026-10-14 02:55에 적용했다. 남은 것은 1주 뒤 같은 대역 허용을 집 안 기기만으로 좁힐지, SSH 키 로그인으로 바꿀지(todo.md "인바운드 가드")
2. **과제 세트 정답 검수**: 100문항. 볼 것은 `experiments/promptsets/llm-tasks-v1/README.md` "검수할 것". 끝나면 `prompts.toml`의 `status`를 `reviewed`로 바꾸고 `round1-tasks`를 밤 타이머에 넣는다. 그 전 결과는 글에 쓰지 않는다
3. **전력계 구입**: 추천은 FNIRSI FNB58을 Pi가 USB로 직접 기록하는 방식(experiments.md 8절). 사면 J/토큰까지 낸다
4. **설계 12절에 남은 것**
   - 모델 8종과 기준 모델(Llama 3.2 1B): 추천대로 진행했다. 바꾸면 `models.toml`과 계획 파일을 고친다
   - `pi-llm` 시리즈를 여는 시점: 추천은 1회차 결과가 커밋되면 연다
   - architecture.md 실험 규칙 두 가지: "1~3B 4비트까지" → "Q4_K_M 기준 2.2GB 이하 파일", "실험 중 에이전트 루프는 쉰다" → "실험이 사이클에 양보한다". 러너는 이미 양보하게 만들었다
5. **커밋 방식**: 문서는 main에 `docs:`, 실험 템플릿·과제 세트·모델 목록은 `exp:`, 러너 코드는 `feat(exp):`로 feat/ 브랜치에서 PR. 요청하면 그렇게 나눈다

## 남은 일

- [ ] 첫 밤 결과 보기: 걸린 시간, 최대 메모리, 온도를 보고 `MemoryMax`, 시간대, 과제 시간 추정을 고친다. HyperCLOVA X SEED가 upstream으로 제대로 도는지도 여기서 본다(계획의 7번 작업)
- [x] `llm-tasks` 러너 (가짜 서버 시험까지). 실제 서버 검증은 `trial-tasks`(밤 타이머)
- [ ] `trial-tasks` 결과 보기: 서버 옵션, 스트리밍, 메모리, 문항당 시간. 1B급 40~60분 추정이 맞는지
- [x] 인바운드 가드 적용 (2026-10-14 02:55, 운영자). 1주 뒤 같은 대역 허용 좁히기, SSH 키 로그인은 todo.md
- [ ] `llm-ppl` 템플릿 (양자화 비교용 퍼플렉서티)
- [ ] 러너를 시스템 서비스로 옮기고 SSH·Caddy·터널의 OOM 우선순위를 낮춘다 (sudo, todo.md "시스템 준비")
- [ ] blogops 실험 툴 3개와 품질 검사 확장 (Phase 2, todo.md)
- [ ] 커밋

## 파일 (모두 커밋 전)

새 파일:

- `docs/experiments.md`
- `experiments/README.md`, `experiments/models.toml`
- `experiments/templates/llm-bench/template.toml`, `experiments/templates/llm-tasks/template.toml`
- `experiments/plans/`: `round1-bench.toml`, `trial-tasks.toml`, `round1-tasks.toml`
- `experiments/runner/`: `common.py`, `telemetry.py`, `llm_bench.py`, `llm_tasks.py`, `night.py`, `fetch_models.py`, `test_runner.py`, `test_score.py`, `test_tasks.py`
- `experiments/promptsets/llm-tasks-v1/`: `README.md`, `prompts.toml`, `score.py`, `t1_schema.json`, `t1_command.jsonl`, `t2_intent.jsonl`, `t3_extract.jsonl`, `t4_answer.jsonl`
- `ops/install-firewall.sh`, `ops/test-firewall.sh`, `ops/firewall/unattendant-guard.nft.in`, `ops/systemd/unattendant-firewall.service`
- 이 문서

고친 파일: `CLAUDE.md`(문서 목록에 experiments.md), `docs/todo.md`(실험 러너 절, 인바운드 가드 절, 열린 질문 "전력 측정"), `ops/README.md`("인바운드 가드 (sudo)")

Pi에 설치된 것(운영자, sudo): `/etc/nftables.d/unattendant-guard.nft`, `/etc/systemd/system/unattendant-firewall.service`(enabled)

레포 밖: `~/opt/llama.cpp/v0.6.0/`(소스, 빌드, `build-configure.log`, `build.log`), `~/models/gguf/`(모델 8종과 `.sha256` 기록), `logs/experiments.jsonl`과 `logs/exp-run.lock`(git 제외)
