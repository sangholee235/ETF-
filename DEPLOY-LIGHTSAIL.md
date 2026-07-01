# AWS Lightsail 배포 가이드 (실제 배포 기록)

autovest 를 AWS Lightsail(서울) + Docker + Tailscale 로 배포한 실제 과정.
서버에서 24시간 봇이 돌고, 대시보드는 Tailscale HTTPS 로만 접근(외부 포트 0개).

---

## 0. 최종 구조
```
AWS Lightsail (서울, Ubuntu 24.04, 1GB/2vCPU)
  ├ Docker: backend(FastAPI) + frontend(nginx)
  ├ 포트: 127.0.0.1:8080 바인딩 (인터넷 노출 0)
  └ 접근: Tailscale serve → https://<host>.<tailnet>.ts.net (내 기기만)
```

## 1. 인스턴스 생성 (Lightsail 콘솔)
- Region: **서울(ap-northeast-2)** — 한국 증권사 API 지연 최소화
- Blueprint: **OS Only → Ubuntu 24.04 LTS**
- Plan: **General purpose $7/월 (1GB RAM, 2 vCPU, 40GB SSD, 2TB)**
- Network: **Dual-stack** (IPv4 필요 — 증권사/GitHub 붙음)
- Launch script / SSH key: 비워둠(기본)

## 2. 고정 IP (Static IP)
- 인스턴스 → **Networking → Attach static IP**
- 인스턴스에 붙여 쓰는 한 **무료**(꺼도 무료). 삭제 후 방치할 때만 과금.
- 재시작해도 IP 안 바뀜 → 키움 IP 등록이 안 깨짐.

## 3. 접속 (브라우저 SSH)
- 인스턴스 → **Connect using SSH** (키파일 불필요, 제일 쉬움)
- 붙여넣기: 리모트 클립보드 칸에 붙여넣고 → 터미널로 넘긴 뒤 **터미널에서 Enter**

## 4. 서버 세팅
```bash
sudo apt update && sudo apt upgrade -y

# 도커
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu      # sudo 없이 쓰려면 재접속 필요

# (선택) 스왑 — 1GB에서 빌드 메모리 스파이크 대비. 넉넉하면 생략 가능
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
> `usermod` 직후 같은 세션은 아직 권한 없음 → `exit` 후 재접속하거나 `sudo docker ...` 로 실행.

## 5. 코드 + 키
```bash
git clone https://github.com/sangholee235/Tossapi.git   # 공개 repo
cd Tossapi
cp .env.example .env
nano .env      # BROKER, 토스/키움 키 입력 (둘 다 쓰면 4개 다 채움)
```
- `.env` 는 git 에 없음(gitignore). `.env.example`(빈 템플릿)만 clone 됨.
- `BROKER=kiwoom|toss` = 기본 브로커. 키가 있는 증권사는 대시보드 토글에 다 뜸.
- 저장: nano 에서 **Ctrl+O → Enter → Ctrl+X**

## 6. ⚠️ 키움 IP 등록 (키움 LIVE 필수)
- 서버 공인 IPv4 확인: `curl -4 ifconfig.me` (또는 Lightsail 콘솔 Public IPv4)
- **키움 개발자센터 → 앱 설정 → 사용 IP** 에 그 IP 등록.
- 안 하면 8050 "지정단말기 인증 실패". 고정 IP 를 등록하면 재시작해도 안 깨짐.

## 7. 실행
```bash
docker compose up -d --build       # 권한 안 먹으면 sudo
docker compose ps                  # backend/frontend Up·healthy 확인
curl -s localhost:8080/api/health  # {"status":"ok"}
```
- 프론트 빌드가 1GB 에선 느림(수 분). 죽으면 스왑 추가.
- `restart: unless-stopped` → 서버 재부팅해도 봇 자동 재기동.

## 8. 안전 접근 (Tailscale)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                  # 뜨는 login 링크로 로그인(브라우저)
tailscale ip -4                    # 100.x.x.x (서버 사설망 주소)
sudo tailscale serve --bg 8080     # https://<host>.<tailnet>.ts.net 로 노출
```
- `serve` 최초 1회는 **tailnet 에서 Serve 활성화**(뜨는 링크 방문) 필요.
- 내 폰/PC 에 **Tailscale 설치 + 같은 계정** → 브라우저 `https://<host>.<tailnet>.ts.net/` 접속.
- Lightsail 방화벽엔 **8080 을 열지 않음**(SSH 22 만). 코드의 127.0.0.1 바인딩 + 방화벽 미개방 = 이중 차단.

## 9. 운영
| 작업 | 방법 |
|---|---|
| 로그 | `docker compose logs -f backend` |
| 업데이트 | `git pull && docker compose up -d --build` |
| 재기동 | `docker compose restart` |
| **긴급정지** | Lightsail 콘솔 **인스턴스 Stop**, 또는 `docker compose stop` |
| 상태·전략 | 대시보드 또는 `bot_data` 볼륨 |

## 10. CI/CD (자동 배포) — GitHub Actions + ghcr.io + Watchtower
흐름: `git push main` → Actions(테스트→이미지 빌드→ghcr.io push) → 서버 Watchtower 가 감지해 자동 교체.
서버로 들어오는 통로 없음(서버가 스스로 pull). 빌드는 CI(빵빵함)에서 → 1GB 서버는 빌드 안 함.

```
push main → Actions: pytest+tsc → 이미지 빌드 → ghcr.io push
                                                │
                          서버 Watchtower(5분) 감지 → 컨테이너 교체(볼륨 유지)
```

### 최초 1회 설정 (서버)
```bash
cd ~/Tossapi
git pull                                   # image: 참조 붙은 compose 받기
# ghcr 패키지가 public 이면 무자격 pull 가능 (아래 주의)
docker compose pull                        # ghcr.io 이미지 당기기
docker compose up -d                       # 당긴 이미지로 실행(빌드 X)
docker compose -f docker-compose.watchtower.yml up -d   # Watchtower 상시 가동
```

### 최초 1회 설정 (GitHub, 브라우저)
- 첫 Actions 실행 후 ghcr 패키지 2개(`tossapi-backend`, `tossapi-frontend`)가 생김.
- **패키지 → Package settings → Change visibility → Public** 로 바꿔야 서버가 **무자격 pull** 가능
  (repo 공개·이미지에 비밀 없음 → public 안전. "서버에 자격증명 0" = 방진 철학 유지).
  비공개로 두려면 서버에 read 토큰으로 `docker login ghcr.io` 필요.

### 이후 배포 = git push 만
```
로컬에서 코드 수정 → git push
→ (자동) Actions 빌드 → ghcr push → Watchtower 5분 내 교체 → 끝
```
상태(bot_data 볼륨)는 교체돼도 유지. 급하면 서버에서 `docker compose pull && docker compose up -d` 수동.

## 함정 (실제로 겪음)
- **`No module named 'brokers'`** — Dockerfile 이 `brokers/` 복사 누락했었음 → `COPY brokers/ ./brokers/` 추가로 해결(수정 완료).
- **`permission denied ... docker.sock`** — `usermod` 후 재접속 안 함 → 재접속 또는 `sudo`.
- **`curl ifconfig.me` 가 IPv6 반환** — `curl -4` 로 IPv4 강제.
- **Tailscale 주소로 접속 안 됨** — 127.0.0.1 바인딩 때문 → `tailscale serve` 로 해결(포트 안 열고 프록시).
- **리모트 클립보드 붙여넣기 후 느낌표만** — 클립보드 칸이 아니라 터미널로 넘긴 뒤 Enter.
