# autovest — 지수 ETF 자동 적립 봇

**"돈만 넣으면 내 목표 비중대로 알아서 리밸런싱하며 적립"** 하는 풀스택 자동매매 시스템.
토스증권·키움증권 Open API 위에, 금융 안전장치와 무인 배포(CI/CD)를 갖춰 24시간 운영된다.

> ⚠️ 교육·연구용 오픈소스. 실주문은 **본인 키·자금·책임** 하에 동작합니다. [DISCLAIMER.md](DISCLAIMER.md) 필독.

---

## 이게 왜 다른가 (증권사 정기적립과의 차이)

증권사 앱에도 "매월 N일 특정 종목 N원 자동매수"는 있다. 이 프로젝트의 차별점은:

> **포트폴리오 비중추종 리밸런싱 적립** — 여러 ETF를 두고, **지금 목표 비중 대비 가장 부족한 ETF를 골라** 산다.
> 돈을 넣을수록 자연스럽게 목표 비중에 수렴/유지된다. (증권사 정기적립은 종목별 독립 매수라 이걸 안 해줌)

- **비중 딱 맞아도 현금을 안 놀림** — 균형 상태면 목표 비중 유지하며 계속 적립
- **여러 증권사 통합** — 토스·키움 한 화면에서 토글 (브로커 추상화로 교체 가능)
- **내 규칙대로** — 지정가 할인·N일 미체결 시 시장가 전환·하루 한도 등 세밀한 제어

---

## 설계 철학 (의도적으로 지킨 것)

- **예측하지 않는다** — LLM·지표 예측 대신 **검증 가능한 규칙을 감정 없이 집행**
- **매도 로직 없음** — 매수전용 적립. 가장 어려운 "언제 파나"를 제거
- **현금 매수만** — 레버리지·공매도 없음 → **최대 손실 = 입금액**. API에 출금 기능도 없음
- **다층 안전장치** — 기본 DRY_RUN(모의), 하루/누적 한도, 장운영시간·잔고 가드레일, 멱등키, 킬스위치
- **검증 우선** — 전략을 과거 데이터로 백테스트 (지정가 적립 vs 단순 적립 평단·수익률 비교)

---

## 아키텍처

```
        ┌──────────────── 프론트 (React+TS, Vite, PWA) ───────────────┐
        │  적립 대시보드: 자산·수익률 · 목표비중 · 전략상태 · 거래내역   │
        └───────────────┬──────────────────────▲─────────────────────┘
                REST /api │           SSE /api/bot/stream (실시간 체결)
        ┌───────────────▼──────────────────────┴─────────────────────┐
        │                    백엔드 (FastAPI)                          │
        │  라우터(market·account·orders·bot) · 스케줄러 · 실시간 ws    │
        │  봇: strategy·guardrails·executor·runner·portfolio·state     │
        │  ── 브로커 추상화 (Broker ABC) ──                            │
        │       ├ TossBroker   (토스 OpenAPI)                          │
        │       └ KiwoomBroker (키움 REST + WebSocket)                 │
        └──────────────────────────────────────────────────────────────┘
```

- **브로커 추상화**: 봇·전략·UI는 `Broker` 인터페이스에만 의존 → `BROKER=toss|kiwoom` 한 줄로 교체
- **응답 정규화**: 키움 REST 응답(0패딩·부호·A접두 종목코드·HHMMSS 시각)을 토스 형태로 통일
- **실시간**: 키움 WebSocket 체결통보 → SSE로 프론트 push → 화면 즉시 갱신 + 디스코드 알림

---

## 주요 기능

| 영역 | 내용 |
|---|---|
| 전략 | 비중추종 적립 · 지정가 할인 · N일 미체결 시 시장가 · 하루/누적 한도 |
| 자동화 | 평일 지정 시각 스케줄러 · 수동 1회 적립 · 킬스위치 |
| 조회 | 실계좌 보유·평가손익·종목별 수익률 · 매수가능금액 · 캔들/호가 |
| 주문 | 매수(지정/시장) · 미체결 조회·**취소** · **거래내역(다일자)** |
| 실시간 | 체결통보(WebSocket→SSE) · 스케줄러/실시간 연결 상태 배지 |
| 알림 | 실제 체결 시 **디스코드** "🟢 체결" (선택) |
| 검증 | 백테스트 + 스윕(최적 할인%/전환일 탐색) · pytest 27케이스 |
| UX | 다크 반응형 · **PWA(홈화면 설치)** · 로딩 스켈레톤 · 점진 렌더링 |

---

## 빠른 시작 (Docker)

```bash
git clone <repo> && cd Tossapi
cp .env.example .env      # BROKER + 토스/키움 키 입력 (+ DISCORD_WEBHOOK_URL 선택)
docker compose up -d --build
# 대시보드: http://localhost:8080  (서버 자신만 접근 — 외부 노출 X)
```

키움을 LIVE로 쓰려면 **서버 공인 IP를 키움 개발자센터에 등록**해야 한다(8050 방지).

### 로컬 개발
```bash
# 백엔드 (Windows 는 PYTHONUTF8=1 권장)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
# 프론트
cd frontend && npm install && npm run dev   # http://localhost:5173 (/api→8000 프록시)
# 테스트
cd backend && python -m pytest tests/ -q
```

---

## 배포 · CI/CD

- **클라우드 상시 운영**: AWS Lightsail + Docker + Tailscale(HTTPS, 내 기기만 접근). 절차·함정은 **[DEPLOY-LIGHTSAIL.md](DEPLOY-LIGHTSAIL.md)**.
- **무인 배포**: `git push` → GitHub Actions(테스트→이미지 빌드→ghcr.io) → 서버 Watchtower 자동 교체. 서버로 들어오는 통로 0개(pull 방식).
- **보안**: 포트 `127.0.0.1` 바인딩 + Tailscale, 로그인 없는 대시보드라 인터넷 전체공개 금지.

---

## 기술 스택

**백엔드** FastAPI · uvicorn · requests · websockets · pytest
**프론트** React 19 · TypeScript · Vite · lightweight-charts · vite-plugin-pwa
**인프라** Docker Compose · GitHub Actions · ghcr.io · Watchtower · Tailscale

---

## 문서

| 문서 | 내용 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | 프로젝트 현황·구조·관례·함정 (이어받는 사람용) |
| [DEPLOY-LIGHTSAIL.md](DEPLOY-LIGHTSAIL.md) | 실제 배포 절차 (Lightsail·Tailscale·CI/CD) |
| [DESIGN-NOTES.md](DESIGN-NOTES.md) | 설계 결정 (심플 vs 방진 모드·GitOps·패키징) |
| [DISCLAIMER.md](DISCLAIMER.md) | 면책 (실주문 책임) |

---

## 상태

핵심 기능(매수전용 비중추종 적립·다중 브로커·실시간·알림)과 무인 CI/CD 배포까지 완료.
현재 심플 모드(셀프호스팅, 폼으로 설정)로 운영하며, 강한 무결성이 필요하면 "방진 모드"(전략을 git으로만 변경)로 확장 가능 — [DESIGN-NOTES.md](DESIGN-NOTES.md) 참고.
