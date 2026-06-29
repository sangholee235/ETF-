# 배포 가이드 (리눅스 서버 + 안전 접근)

봇은 서버에서 24시간 자동으로 돈다. UI는 본인만 안전하게 접속한다.
대시보드에 로그인이 없으므로 **절대 포트를 인터넷에 전체공개(0.0.0.0)하지 말 것.**

추천: **Oracle Cloud Always Free**(영구 무료 ARM) 또는 EC2/Lightsail. OS는 Ubuntu 22.04+.

---

## 1. 서버 기본 세팅
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl
```

## 2. 도커 설치
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker compose version   # 확인
```

## 3. 코드 + 키
```bash
git clone https://github.com/sangholee235/Tossapi.git
cd Tossapi
cp .env.example .env
nano .env     # BROKER, 토스/키움 키 입력
```
`.env` 예:
```
BROKER=kiwoom
KIWOOM_APP_KEY=...
KIWOOM_SECRET_KEY=...
TOSS_CLIENT_ID=...
TOSS_CLIENT_SECRET=...
```

## 4. ⚠️ 키움 IP 등록 (키움 쓸 때 필수)
키움 8050(지정단말기) 방지 — **이 서버의 공인 IP**를 키움 개발자센터에 등록.
```bash
curl ifconfig.me     # 서버 공인 IP 확인 → 키움에 등록
```

## 5. 실행
```bash
docker compose up -d --build
docker compose ps                 # backend healthy / frontend up
docker compose logs -f backend    # 로그 (Ctrl+C로 나옴)
```
이 시점부터 봇이 24시간 자동 적립. 포트는 서버 자신(127.0.0.1)만 열려 외부 노출 없음.

## 6. 방화벽 (SSH만 허용)
```bash
sudo ufw allow 22/tcp
sudo ufw enable
```

---

## 7. UI 접근 — 둘 중 택 1

### A. SSH 터널 (제일 간단·안전)
**내 PC에서:**
```bash
ssh -L 8080:localhost:8080 ubuntu@<서버IP>
# 연결한 채로 브라우저 → http://localhost:8080
```
포트를 인터넷에 안 열고, 볼 때만 터널.

### B. Tailscale (폰 포함, 어디서나)
**서버:**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                 # 브라우저로 구글/애플 계정 로그인
sudo tailscale serve --bg 8080    # tailnet 에 HTTPS 로 노출
```
**내 폰/노트북:** Tailscale 앱 설치 → **같은 계정 로그인** → 브라우저로 서버의 tailnet 주소 접속.
포트 0개 공개, 내 기기만 접근.

---

## 운영
| 작업 | 명령 |
|---|---|
| 끄기 | `docker compose down` |
| 켜기 | `docker compose up -d` |
| 업데이트 | `git pull && docker compose up -d --build` |
| 로그 | `docker compose logs -f backend` |
| 봇 상태/전략 | 대시보드 또는 `bot_data` 볼륨 |

- 재부팅돼도 자동 재시작(`restart: unless-stopped`).
- 전략·체결기록은 `bot_data` 볼륨에 영속 → 재배포해도 유지.
- `.env`·`bot_config_*.json`은 git 제외(각자 서버에만).

## 자주 막히는 곳
| 증상 | 해결 |
|---|---|
| `docker: permission denied` | `newgrp docker` 또는 재로그인 |
| 키움 토큰 8050 | 서버 공인 IP를 키움에 등록 |
| 8080 접속 안 됨 | SSH 터널 연결했는지(localhost:8080) / Tailscale 켰는지 |
| ARM 빌드 | Oracle ARM VM은 이미지가 ARM 지원이라 OK |

## ⚠️ 보안
- `127.0.0.1:8080` 유지 (절대 `0.0.0.0` 금지) — 대시보드에 로그인이 없어 공개 시 계좌·주문이 노출됨.
- 외부 접근은 SSH터널/Tailscale로만.
- 봇은 매수전용·현금계좌라 최대 손실 = 입금액 (출금 API 없음).
