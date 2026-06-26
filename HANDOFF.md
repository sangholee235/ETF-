# 프로젝트 핸드오프 (다음 작업자용)

당신은 이 프로젝트를 이어받는다. 아래는 지금까지의 맥락·구조·관례·함정·다음 할 일이다.
사용자는 한국어로 대화하며, 빠르고 명확한 진행을 선호한다(말 길게 늘어놓는 것 싫어함).

---

## 0. 한 줄 요약
토스증권/키움증권 Open API로 **지수 ETF 매수전용(buy-only) 자동 적립 봇** + 토스앱풍 대시보드.
풀스택: **React+TS(Vite) 프론트 / FastAPI 백엔드**. 증권사는 **브로커 추상화로 교체 가능**.

## 1. 핵심 설계 철학 (사용자와 합의된 것 — 지키기)
- **예측하지 않는다.** LLM·지표로 시장 예측 X. 검증 가능한 규칙을 감정 없이 집행.
- **매수전용, 안 판다.** 매도 로직 없음 → 최대 손실 = 입금액. (지수 ETF라 상장폐지 위험도 없음)
- **다층 안전장치**: 기본 DRY_RUN(모의), 하루 한도, 장운영시간·잔고 가드레일, 멱등키, 킬스위치.
- **검증 우선**: 백테스트/스윕으로 전략을 과거 데이터로 확인. (상승장에선 지정가적립이 단순적립을 못 이긴다는 게 데이터로 증명됨)
- 전략: *매일 1주, 전일종가 −X% 지정가, N일 미체결 시 시장가, 포트폴리오 모드면 목표비중 대비 가장 부족한 ETF 선택.*

## 2. 디렉터리 구조
```
Tossapi/
  .env               # 키 (git 제외). 토스/키움 키 + BROKER 선택
  docker-compose.yml # 원클릭 배포 (backend + frontend nginx)
  backend/
    Dockerfile  requirements.txt
    tossapi/         # 토스 클라이언트 라이브러리 (config/auth/client/errors)
    brokers/         # ★ 증권사 추상화
      base.py        # Broker ABC (17개 메서드 인터페이스)
      toss.py        # TossBroker(TossClient, Broker) — 토스 (완성)
      kiwoom.py      # KiwoomBroker — 키움 REST (부분 구현, 진행중)
      __init__.py    # get_broker(): BROKER=toss|kiwoom (.env 먼저 로드함)
    app/
      main.py        # FastAPI + CORS + 스케줄러 lifespan
      deps.py        # get_client()=get_broker() 싱글턴, 에러변환
      routers/       # market, account, orders, bot
      bot/           # config, strategy, guardrails, executor, runner,
                     # scheduler, backtest, portfolio, catalog, state
      market_ranking.py  # 랭킹/지수요약 (큐레이션 유니버스)
    scripts/kiwoom_test.py  # 키움 토큰 발급 테스트
    tests/           # pytest 20개 (전략/가드레일/백테스트/포트폴리오)
  frontend/
    Dockerfile  nginx.conf
    src/ App.tsx api.ts types.ts App.css
         Chart.tsx OrderbookLadder.tsx HoldingsDonut.tsx
         RankingPanel.tsx MarketBar.tsx
         BotPanel.tsx PortfolioPanel.tsx Backtest.tsx Sweep.tsx
         AvgPriceChart.tsx LogsPanel.tsx
```

## 3. 실행
```bash
# 백엔드 (PYTHONUTF8=1 필수 — Windows 한글깨짐 방지)
cd backend && PYTHONUTF8=1 python -m uvicorn app.main:app --reload --port 8000
# 프론트
cd frontend && npm run dev          # http://localhost:5173 (vite proxy /api→8000)
# 테스트
cd backend && python -m pytest tests/ -q
# 도커 (검증됨)
docker compose up -d                # http://localhost:8080
```

## 4. 화면 (탭 4개)
- **조회**: 자산 히어로(평가/손익) · 시세표+호가1 · 캔들차트(MA20+거래량) · 미체결 · 보유비중 도넛 · 보유표
- **랭킹**(토스 메인풍): 지수 바(스파크라인) · 선택종목 헤더 · 차트+호가창 · 거래대금/시총 랭킹
- **적립봇**: 상태(DRY/LIVE·킬스위치) · ETF선택 · 포트폴리오(목표비중 도넛) · 전략/한도 · 스케줄 · 백테스트 · 스윕 · 차트 · 로그
- **로그**: 봇 실행 기록 필터

## 5. 브로커 구현 현황 (★ 현재 진행중 = 키움 통합)
토스: **전부 구현·동작.** 키움(REST, `BROKER=kiwoom`): 응답을 **토스 형태로 정규화**하는 게 핵심 작업.

| 기능 | 토스 | 키움 TR | 키움 상태 |
|---|---|---|---|
| 토큰 | OAuth2 | au10001 | ✅ |
| 계좌 | ✅ | ka00001 | ✅ (`acctNo`) |
| 호가 | ✅ | ka10004 | ✅ (10단계, sel_fpr/sel_Nth, buy_fpr/buy_Nth) |
| 현재가 | ✅ | ka10006 | ✅ (`close_pric`, 부호제거) |
| 보유/잔고 | ✅ | kt00018 | ✅ (`acnt_evlt_remn_indv_tot`, 0패딩·% 변환) |
| 일봉차트 | ✅ | ? (차트 카테고리) | ⬜ 다음 할 일 |
| 매수가능금액 | ✅ | kt00010 추정 | ⬜ |
| 종목정보(이름) | ✅ | ? (종목정보) | ⬜ (시세표 이름이 코드로 나옴) |
| 주문/조회/취소 | ✅(클라) | 주문 카테고리 | ⬜ 맨 나중, 실거래라 1주 소액 |

키움 정규화 관례(kiwoom.py 참고):
- 종목코드 `A005930` → `005930` (lstrip "A")
- 숫자 0패딩 문자열 → `_i()` (int 변환), 부호숫자 → `_absnum()`, 수익률 % → `_rate()` (÷100)
- 응답은 HTTP 200이어도 `return_code != 0`이면 실패 → `_request()`가 검사함
- 공통 호출: `_request(api_id, "/api/dostk/...", body={...})`

## 6. 함정 / 주의 (실제로 겪은 것)
- **PYTHONUTF8=1** 없으면 Windows 콘솔 한글 깨짐.
- **포트 8000 ghost socket**: 가끔 kill 후에도 LISTENING 잔존 → `Get-Process python | Stop-Process -Force`로 정리.
- **백엔드 --reload 안 쓰면** 코드 바꿔도 반영 안 됨. TR 추가 후 반드시 재시작/리로드.
- **get_broker()는 .env를 먼저 로드**해야 BROKER를 읽음 (안 그러면 toss로 폴백). 이미 수정됨.
- **그리드 오버플로**: 2컬럼은 `minmax(0,1fr)` + 카드 `min-width:0` 필수.
- **차트 무한확장**: lightweight-charts `autoSize` + flex 컨테이너 = 피드백 루프. 높이 360 고정 + 너비만 ResizeObserver.
- **rate limit(429)**: 대시보드 호출 많음. 자동갱신 8초, 랭킹 백엔드 60초 캐시. 친절한 에러 매핑 있음.
- **키움 8050 "지정단말기 인증 실패"**: 코드 문제 아님. 키움 개발자센터에서 **접속 IP 등록**하면 해결됨(사용자가 함).
- 토스 API 한계: 수급(기관/외국인)·웹소켓·ISA·출금 없음. 그래서 랭킹은 큐레이션 유니버스로 흉내냄. **키움은 순위정보·기관외국인 카테고리가 있어** 나중에 진짜로 구현 가능.

## 7. 보안 / 법적 (사용자와 논의됨)
- 키는 `.env`에만(절대 채팅·git 금지). **채팅에 한번 노출된 키는 운영 전 재발급 권장.**
- 서비스화: **각자 자기 키로 자기 환경에서 실행(오픈소스 셀프호스팅)** 이 법적으로 안전. 호스팅+대신매매=투자일임업 규제. UI만 호스팅+IP입력은 HTTPS 혼합콘텐츠로 막힘 → docker 번들 또는 데스크탑앱이 답.
- 배포는 Oracle Cloud **Always Free**(영구무료 ARM) 또는 EC2/Lightsail. 접근은 SSH터널/Tailscale/방화벽(내IP만)으로 — 트레이딩 대시보드라 전체공개 금지.

## 8. 다음 할 일 (우선순위)
1. **키움 일봉차트 TR** 구현 → 조회/랭킹 차트의 "Internal Server Error" 해결 (차트 카테고리, URL 추정 `/api/dostk/chart`)
2. **키움 매수가능금액**(kt00010) → 히어로 "매수가능" 채움
3. **키움 종목정보**(이름) → 시세표 종목명
4. (나중) 키움 주문 — 실거래라 1주 소액, 읽기 다 된 뒤
5. (보너스) 키움 순위정보/기관외국인 → 토스 한계였던 진짜 랭킹·수급

## 9. 사용자 정보
- 소액 실거래로 검증할 계획(키움 모의투자는 안 씀 → 주문 테스트는 진짜 돈, 1주 소액 필수).
- 토스 종합계좌(13501006210), 키움 계좌(6674517110) 둘 다 현금 거의 0.
- 봇은 기본 DRY_RUN 유지 권장. LIVE 전환은 사용자가 직접.

## 10. 작업 방식 (사용자 선호)
- 변경 후 **타입체크(tsc)·테스트·헤드리스 크롬 스크린샷으로 자가검증** 후 보고. (Chrome: `--headless=new --screenshot`)
- 키움 TR은 사용자가 명세(요청/응답 예시) 주면 정규화 구현. **api-id 모르면 후보를 직접 호출해 탐색**(읽기 TR은 안전).
- 명세 없이 필드명 지어내지 말 것(환각 → 틀린 주문 위험).
