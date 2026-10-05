# ops

Pi에서 블로그를 띄우는 데 필요한 설정과 설치 기록. 다른 프로젝트(TrueETA 등)의 서비스·포트는 건드리지 않는다.

## 구성

| 파일 | 역할 |
| --- | --- |
| `install-site-tools.sh` | Hugo extended, Caddy를 GitHub 릴리스 arm64 바이너리로 `~/.local/bin`에 설치 (체크섬 검증, sudo 불필요) |
| `caddy/Caddyfile` | `site/public`을 `127.0.0.1:8080`에 서빙. TLS는 Cloudflare가 맡는다 |
| `systemd/unattendant-caddy.service` | Caddy 상시 실행 |
| `cloudflared/config.yml` | Named Tunnel `unattendant` ingress (`unattendant.dev` → `127.0.0.1:8080`) |
| `systemd/unattendant-tunnel.service` | 터널 상시 실행 |

## 사이트 빌드

```bash
cd ~/unattendant/site && hugo --gc --minify --cleanDestinationDir
```

Caddy는 `public/`을 바로 읽으므로 빌드 후 재시작은 필요 없다.

## 서비스 설치 (sudo)

```bash
cd ~/unattendant
sudo install -m 644 ops/systemd/unattendant-caddy.service ops/systemd/unattendant-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now unattendant-caddy
# 터널은 아래 Named Tunnel 준비 후
sudo systemctl enable --now unattendant-tunnel
```

## Named Tunnel 준비 (한 번만)

2026-10-06 확인: 이 Pi에는 Named Tunnel이 없었다. TrueETA는 Quick Tunnel(`trueeta-tunnel.service`, 현재 disabled)만 썼고 `~/.cloudflared/`도 없었다. 그래서 unattendant 전용 Named Tunnel을 새로 만들었다(id `bd749433-fd2f-48ba-b325-ff2115f1a40d`, 2026-10-06).

```bash
cloudflared tunnel login                         # 브라우저에서 unattendant.dev 존 선택 → ~/.cloudflared/cert.pem
cloudflared tunnel create unattendant            # ~/.cloudflared/<UUID>.json 생성 (비밀값, 커밋 금지)
cloudflared tunnel route dns unattendant unattendant.dev
# cloudflared/config.yml의 TUNNEL_UUID를 실제 UUID로 바꾼다
cloudflared --config ~/unattendant/ops/cloudflared/config.yml tunnel ingress validate
```

## 버전 기록

| 도구 | 버전 | 설치일 |
| --- | --- | --- |
| Hugo extended | 0.167.0 | 2026-10-06 |
| Caddy | 2.11.7 | 2026-10-06 |
| cloudflared | 2026.9.1 (deb, `/usr/bin`) | 기존 |
