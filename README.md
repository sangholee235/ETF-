# Tossapi

토스증권 Open API 를 활용한 자동 매매 프로그램.
**프론트엔드(React + TypeScript) / 백엔드(FastAPI)** 구조.

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

## 로드맵

1. ✅ API 조회 클라이언트 (인증 + 시세/계좌/자산)
2. ✅ React + FastAPI 구조 + 조회 대시보드
3. ⬜ LLM 기반 매매 판단 (모의 모드부터)
4. ⬜ 실주문 + 리스크 가드레일 (한도/유의종목/장운영시간)
