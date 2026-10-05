# unattendant.dev 하드웨어 구성 논의 정리

> 2026-10-05 세션 논의 요약. 엣지 AI 실험 블로그를 위한 장비 역할 분담과 원격 전원 제어(WOL) 운용 방안.

## 1. 장비 목록과 역할

| 장비 | 사양 | 역할 | 운용 |
|---|---|---|---|
| Raspberry Pi 4 (4GB) | ARM, 4GB | 블로그 퍼블리셔 + 엣지 AI 실험 대상 (주인공) | 상시 가동 |
| LG 울트라PC 15U480-KA56K (2018) | i5-8250U, 8GB, MX150 2GB, Realtek 유선랜, Ubuntu 22.04 듀얼부팅 | 상시 백엔드 또는 오프로딩 실험 대상 (선택) | 상시 또는 필요할 때 |
| 게이밍 데스크탑 | Ryzen 7 7800X3D, 32GB, RTX 4070 Ti 12GB, Windows | 무거운 작업 서버 (양자화·변환·파인튜닝·라벨링) | WOL로 필요할 때만 |
| Google Colab | 무료 T4 | 블로그 독자용 재현 노트북 | 글마다 링크 첨부 |

**한 줄 요약: Pi가 주인공, 데스크탑이 작업장, Colab은 독자용.**

## 2. 기본 원칙

- 글의 주인공은 계속 Pi. 독자가 궁금한 건 "Pi에서 되냐, 얼마나 빠르냐"다.
- "Pi vs i5 vs MX150 속도 비교"를 매번 하는 건 피한다. 결과가 뻔하다.
- 다른 장비는 **만드는 곳**(변환, 양자화, FP32 정확도 기준값)이자 **넘겨받는 곳**(오프로딩 서버)으로 쓴다.

### 노트북/서버가 의미 있는 실험

1. 모델 변환·양자화 (예: YOLOv8n FP32 → INT8, Pi 속도 향상 대비 정확도 손실)
2. 정확도 기준점: 원본 FP32 결과를 레퍼런스로 사용
3. 오프로딩 실험: Pi 단독 / Pi + 로컬 서버(LAN) / Pi + 클라우드 API 비교. WOL 기상 시간까지 포함한 지연·전력 트레이드오프
4. 데이터 자동 라벨링 (MX150은 범위가 제한적이고, 데스크탑이 적합)

## 3. WOL 원격 전원 제어 흐름

```
Pi                                    대상 머신
 │── ① WOL 매직패킷 (MAC) ──────────▶ 전원 켜짐/부팅
 │── ② ping/SSH 될 때까지 폴링 ─────▶ (부팅 30~60초)
 │── ③ SSH로 작업 실행 (타임아웃 필수) ▶ 작업 스크립트
 │◀── ④ 결과 회수 (scp/rsync) ───── 결과 파일
 │── ⑤ SSH로 종료 또는 절전 ────────▶ 전원 꺼짐
```

```bash
#!/bin/bash
HOST=192.168.0.50; MAC=aa:bb:cc:dd:ee:ff
wakeonlan $MAC
for i in {1..60}; do ssh -o ConnectTimeout=2 lab@$HOST true && break; sleep 5; done
ssh lab@$HOST 'timeout 2h ~/bench/run.sh'
scp lab@$HOST:~/bench/results.json ./results/
ssh lab@$HOST 'sudo systemctl poweroff'
```

공통 안전장치:

- 작업에 타임아웃을 건다.
- 대상 머신 쪽에도 "N시간 후 자동 종료" 같은 장치를 하나 더 둔다.
- SSH는 키 인증만 허용하고 내부망에서만 연다.

## 4. 노트북 (LG 15U480) 세팅

### 확인된 사실

- 내장 RJ45 유선랜이 있고, 칩은 Realtek PCIe GbE라서 칩 자체는 WOL을 지원한다.
- 꺼진 상태(S5)에서 WOL이 되는지는 **미확인**이다. LG BIOS는 설정 항목이 적어서 안 될 가능성이 있다. 절전(S3) WOL은 될 가능성이 높다.

### WOL 테스트 순서

1. AC 어댑터와 랜선을 연결한다.
2. BIOS(F2)에서 WOL 관련 항목이 있는지 확인한다.
3. 절전 상태에서 `wakeonlan <MAC>`을 보내 S3를 확인한다.
4. 완전히 끈 상태에서 `wakeonlan <MAC>`을 보내 S5를 확인한다.

결과별 운용:

- **S5까지 됨**: 켜고, 작업하고, 끈다.
- **S3만 됨**: 절전으로 운용한다(`systemctl suspend`). 대기 전력은 1W 안팎이다.
- **둘 다 안 됨**: 상시로 켜두고 저전력으로 운용한다(아이들 5~8W).

### Ubuntu 22.04 운용 체크리스트

1. **GRUB 기본 부팅을 우분투로 설정**: `GRUB_DEFAULT=0`, `GRUB_TIMEOUT=3`, `sudo update-grub`. Windows 빠른 시작은 끈다.
2. **WOL 영구 설정**: `sudo nmcli c modify "Wired connection 1" 802-3-ethernet.wake-on-lan magic`. `ethtool`에서 `Wake-on: g`인지 확인한다.
3. **Realtek 드라이버**: `r8169`에서 S5 WOL이 안 되면 `r8168-dkms`로 교체해서 다시 테스트한다.
4. **덮개 닫힘 무시**: `/etc/systemd/logind.conf`에 `HandleLidSwitch=ignore`, `HandleLidSwitchExternalPower=ignore`를 설정한다.
5. **절전 모드**: `/sys/power/mem_sleep`을 확인하고, 필요하면 `mem_sleep_default=deep`을 설정한다.
6. **권한**: Pi SSH 키를 등록하고 sudoers에 `lab ALL=NOPASSWD: /usr/bin/systemctl poweroff, /usr/bin/systemctl suspend`를 추가한다.
7. **MX150**: `sudo ubuntu-drivers install` 후 `nvidia-smi`로 확인하고, `prime-select on-demand`로 둔다.

### 상시 서버로 쓸 때

이점:

- Pi의 부담을 줄여준다. DB, 모니터링, 대시보드, 작업 큐를 맡기면 벤치마크 수치도 덜 오염된다.
- SSD에 데이터를 둬서 Pi SD카드 마모를 방지한다.
- 내장 배터리가 UPS 역할을 한다.
- 데스크탑 WOL 발송과 작업 큐 관리를 맡는 관제탑이 될 수 있다.
- 임베딩이나 작은 모델 추론 같은 가벼운 AI 작업을 상시 처리할 수 있다.
- 오프로딩 실험 대상으로 바로 쓸 수 있다.

주의:

- **배터리 부풀음**: 80% 충전 제한(LG Control Center)이 우분투에서도 유지되는지 확인해야 한다. 안 되면 배터리를 분리하고 AC만으로 운용한다.
- 아이들 6~10W 정도라 전기료는 월 천 원 안팎이다.
- 팬 청소나 서멀 재도포를 고려한다.
- "Pi 한 대가 운영한다"는 컨셉이 흐려질 수 있어서 역할 분리를 명확히 한다.

권장: Pi 단독으로 시작하고, 메모리나 SD카드가 한계에 닿으면 노트북을 투입한다. 그 과정 자체가 글감이 된다.

## 5. 데스크탑 (Windows) 세팅

Windows + WSL2로 충분하다. 듀얼부팅은 필수가 아니다.

- WSL2에서 CUDA가 동작한다. PyTorch, ONNX Runtime 양자화, TFLite 변환, Ultralytics export를 쓸 수 있다.
- NPU 변환 툴킷(Hailo, RKNN 등)도 대부분 WSL2 우분투에서 동작한다.

### 자동화 흐름

1. Pi가 WOL을 보낸다.
2. Windows OpenSSH 서버로 접속한다.
3. `wsl -e bash -lc "~/jobs/quantize.sh model.pt"`를 실행한다.
4. scp로 결과를 회수한다.
5. `shutdown /s /t 0`으로 끈다.

### 체크리스트

- [ ] Windows 빠른 시작 끄기
- [ ] BIOS: ErP 끄기, Wake on LAN(Power On by PCI-E) 켜기
- [ ] 랜카드 "Wake on Magic Packet" 켜기
- [ ] Windows 업데이트 자동 재부팅 방지 (사용 시간 설정)
- [ ] 게임 중 보호: 작업 전에 `nvidia-smi`나 게임 프로세스를 확인하고, 사용 중이면 작업을 미루고 끄지 않기
- [ ] SSH 키 인증만 허용, 내부망 전용
- [ ] 아이들 전력이 크므로 작업 후 자동 종료 필수

## 6. Colab을 자동화 파이프라인으로 쓰지 않는 이유

- Pi에서 API로 Colab을 실행하고 결과를 받는 무인 자동화는 공식 지원되지 않는다.
- 세션 끊김과 GPU 할당이 불확실하고, 무료 티어 정책에 걸릴 위험이 있다.
- 그래서 독자 재현용 노트북으로만 쓴다.

## 7. 다음 할 일

- [ ] 노트북 S3/S5 WOL 테스트 → 결과에 따라 운용 방식 결정
- [ ] 데스크탑 BIOS/Windows WOL 설정 후 테스트
- [ ] Pi WOL + 작업 디스패치 스크립트 작성 (게임 중 체크 포함)
- [ ] 첫 실험 후보: YOLOv8n FP32 vs INT8 on Pi 4 (변환은 데스크탑, 정확도 기준값 포함)
