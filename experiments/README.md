# experiments/

Pi 4B에서 직접 재는 엣지 AI 실험의 템플릿, 모델 목록, 러너, 결과다. 설계와 이유는 [docs/experiments.md](../docs/experiments.md)에 있다.

```
experiments/
├── models.toml              # 모델 목록 (저장소 커밋과 sha256 고정). 사람이 고친다
├── templates/               # 템플릿 정의(llm-bench, llm-tasks): 허용 범위와 고정값
├── promptsets/              # 과제 세트(llm-tasks-v1): 문항, 지시문·예시, 채점기
├── plans/                   # 계획: 밤에 차례로 돌 작업 목록
├── runner/                  # 러너, 공통 로거, 무효 판정, 모델 받기, 시험
└── results/<템플릿>/         # 결과 (공개). summary.csv가 글과 품질 검사가 보는 값
```

레포 밖에 두는 것: 모델 파일 `~/models/gguf/`, llama.cpp 빌드 `~/opt/llama.cpp/<태그>/`, 러너 기록 `logs/experiments.jsonl`·`logs/exp-plans/`(git 제외).

## 준비

```bash
# 모델 받기 (받은 파일은 남이 만든 데이터라 -I로 실행한다)
python3 -I experiments/runner/fetch_models.py --group round1
python3 -I experiments/runner/fetch_models.py --check      # 해시를 다시 계산해 대조

# llama.cpp (2026-10-14: v0.6.0, d812350). 빌드 옵션과 CPU 감지 결과는 build-configure.log에 남는다
git clone --depth 1 --branch v0.6.0 https://github.com/ggml-org/llama.cpp ~/opt/llama.cpp/v0.6.0
cd ~/opt/llama.cpp/v0.6.0
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF > build-configure.log 2>&1
systemd-run --user --scope -p MemoryMax=1536M -- nice -n 10 \
  cmake --build build -j2 --target llama-bench llama-server llama-cli llama-perplexity
```

## 실행

실험은 systemd 유닛 안에서 메모리 상한을 걸고만 돈다(CLAUDE.md). 러너는 상한이 없으면 시작하지 않는다. VS Code 원격 서버가 떠 있으면 시작하지 않고 기다린다.

```bash
# 작업 하나 (속도, 품질)
systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 -p OOMScoreAdjust=500 \
  --working-directory="$PWD" python3 experiments/runner/llm_bench.py --model llama-3.2-1b
systemd-run --user --wait -p MemoryMax=2500M -p MemorySwapMax=0 -p OOMScoreAdjust=500 \
  --working-directory="$PWD" python3 experiments/runner/llm_tasks.py --model llama-3.2-1b   # --json-constraint, --thinking

# 밤 실행 (매일 02:00~05:30): 사용자 매니저 유닛을 설치한다. 재부팅해도 남는다
ops/install-exp-timer.sh                        # ops/systemd/user/exp-night.* → ~/.config/systemd/user/, 타이머 켜기
systemctl --user list-timers exp-night.timer   # 다음 실행 시각
journalctl --user-unit=exp-night.service       # 실행 기록 (logs/experiments.jsonl에도 남는다)
systemctl --user stop exp-night.timer           # 오늘 예약만 멈춘다 (다시 켜기: start)
ops/install-exp-timer.sh --remove               # 타이머를 끄고 유닛을 지운다
```

- 돌릴 계획은 `ops/systemd/user/exp-night.service`의 `--plan`이다(여러 번 주면 차례로 돈다. 지금은 `round1-bench` → `trial-tasks`). 바꾸면 설치 스크립트를 다시 돌린다.
- 놓친 실행은 따라잡지 않는다(`Persistent=false`). `--until`은 "다음 05:30"이라 낮에 시작하면 다음 날 새벽까지 돌기 때문이다. 같은 이유로 낮에 `systemctl --user start exp-night`로 손으로 시작하지 않는다.
- 작업실(`~/unattendant`)에서 돈다. 02:00에 작업실이 실험 파일이 없는 브랜치에 있으면 실패하고 다음 밤에 다시 돈다.
- 사용자 매니저는 tty1 자동 로그인 세션이 붙잡고 있다(`Linger=no`). 시작 조건이 안 맞으면 `night-wait` 기록에 사유가 남는다.
- 2026-10-14부터 10-19까지는 같은 설정을 임시 유닛(`systemd-run --user --on-calendar`)으로 돌렸는데, 재부팅하면 사라져서 바꿨다(2026-10-22).

## 시험

모델을 돌리지 않는다. llama-bench와 llama-server 자리에 가짜 스크립트를 쓴다.

```bash
python3 -m unittest discover -s experiments/runner -p 'test_*.py'
```
