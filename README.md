# Tossapi — 토스증권 Open API 자동 적립 봇

토스증권 Open API 로 **지수 ETF 를 규칙대로 자동 적립**하는 풀스택 애플리케이션.
**React + TypeScript (프론트) / FastAPI (백엔드)** · 다크 반응형 UI · 캔들 차트 · 백테스트 · 스케줄러.

> ⚠️ 교육·연구용 오픈소스. 실주문은 본인 키·자금·책임 하에 동작합니다. [DISCLAIMER.md](DISCLAIMER.md) 필독.

## 설계 의도 (왜 이렇게 만들었나)

이 프로젝트는 "AI/봇이 시장을 예측해 돈을 번다"를 **의도적으로 지양**합니다.

- **예측하지 않는다** — LLM·지표 예측 대신, 검증 가능한 **규칙을 감정 없이 집행**.
- **매도 로직 없음** — 매수전용 적립. 가장 어려운 "언제 파나" 판단을 제거.
- **현금 매수만** — 레버리지·공매도 없음 → **최대 손실 = 입금액**. API 에 출금 기능도 없음.
- **다층 안전장치** — 기본 DRY_RUN(모의), 하루 한도, 장운영시간·잔고 가드레일, 멱등키, 킬스위치.
- **검증 우선** — 전략을 과거 데이터로 백테스트해 "지정가 적립 vs 단순 적립" 평단/수익률 비교.

전략: *매일 1주, 전일종가 −X% 지정가 매수, N일 미체결 시 시장가(상승장 누락 방지), 매도 없음.*

## 화면

- **조회** — 계좌/잔고, 실시간 시세·호가, 캔들 차트(MA20·거래량)
- **적립봇** — ETF 선택, 전략/한도 설정, DRY_RUN↔LIVE, 백테스트(+평단 추이 차트), 자동 스케줄
- **로그** — 전체 실행 기록(모드·액션·체결·사유) 필터링

## 테스트

```bash
cd backend && python -m pytest tests/ -q   # 전략·가드레일·백테스트 14 케이스
```

## 구조

```
Tossapi/
├── .env                      # 인증 키 (git 제외)
├── backend/                  # FastAPI
│   ├── requirements.txt
│   ├── tossapi/              # 토스 API 클라이언트 라이브러리
│   │   ├── config.py  auth.py  client.py  errors.py
│   └── app/
│       ├── main.py           # FastAPI 앱 + CORS
│       ├── deps.py           # TossClient 싱글턴 / 에러 변환
│       └── routers/          # market, account, orders
└── frontend/                 # React + TypeScript (Vite)
    └── src/
        ├── App.tsx  api.ts  types.ts  App.css
```

## 1. 설정

```bash
cp .env.example .env     # .env 에 client_id / client_secret 입력
```

## 2. 백엔드 실행 (터미널 A)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
# API 문서: http://127.0.0.1:8000/docs
```

## 3. 프론트엔드 실행 (터미널 B)

```bash
cd frontend
npm install
npm run dev
# 대시보드: http://localhost:5173  (/api 는 백엔드로 프록시됨)
```

## 주요 엔드포인트 (백엔드)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | /api/health | 헬스체크 |
| GET | /api/market/prices?symbols= | 현재가 (다건) |
| GET | /api/market/orderbook?symbol= | 호가 |
| GET | /api/market/candles?symbol=&interval= | 캔들 |
| GET | /api/market/stocks?symbols= | 종목정보 |
| GET | /api/account/accounts | 계좌목록 |
| GET | /api/account/holdings | 보유주식 |
| GET | /api/account/buying-power?currency= | 매수가능금액 |
| GET | /api/orders?status= | 주문목록 |

> 실주문(생성/정정/취소)은 `backend/app/routers/orders.py` 에 막아둠. 2단계에서 가드레일과 함께 활성화.

## 적립봇 (매수전용 지수 ETF DCA)

예측하지 않고 규칙을 감정 없이 집행하는 매수전용 봇.
매도 없음 / 현금매수만 → 최대손실 = 입금액.

```
backend/app/bot/
  config.py    strategy.py   guardrails.py
  executor.py  runner.py     catalog.py   state.py
  __main__.py  # CLI
```

전략: 매일 1주, 전일종가 -X% 지정가, N일 미체결 시 시장가(상승장 누락 방지).
안전: 기본 DRY_RUN(실주문X), 하루 한도, 장운영시간/잔고 가드레일, 멱등키, 킬스위치.

CLI (backend 디렉터리):
```bash
python -m app.bot status   # 상태
python -m app.bot run      # 적립 1회 (기본 DRY_RUN)
python -m app.bot stop     # 킬스위치
```
대시보드: http://localhost:5173 → "적립봇" 탭 (ETF 클릭 선택 / 한도 설정 / LIVE 전환 / 로그).

> LIVE 전환은 대시보드 버튼 또는 `bot_config.json` 의 `dry_run:false`.
> 누적 한도는 `total_budget_krw:0` = 무제한 (하루 한도만 적용).

## 로드맵

1. ✅ API 조회 클라이언트 (인증 + 시세/계좌/자산)
2. ✅ React + FastAPI 구조 + 조회 대시보드
3. ✅ 매수전용 적립봇 (전략 + 가드레일 + DRY_RUN/LIVE + 대시보드 탭)
4. ✅ 백테스트 (지정가 적립 vs 단순 적립, 평단/수익률 비교) — `GET /api/bot/backtest`
5. ✅ 다크모드 + 반응형 UI + 캔들차트(MA20·거래량, lightweight-charts)
6. ✅ 스케줄러 (평일 지정 시각 자동 적립) + 로그 페이지
7. ✅ 백엔드 테스트(pytest) + 백테스트 평단 추이 시각화
8. ⬜ Docker Compose 원클릭 배포
