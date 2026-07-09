# 프로젝트 핸드오프 (다음 작업자용)

당신은 이 프로젝트를 이어받는다. 아래는 지금까지의 맥락·구조·관례·함정·다음 할 일이다.
사용자는 한국어로 대화하며, 빠르고 명확한 진행을 선호함

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
  .env                        # 키 (git 제외). 토스/키움 키 + BROKER + DISCORD_WEBHOOK_URL
  docker-compose.yml          # backend + frontend. image:(ghcr) + build:(로컬) 둘 다
  docker-compose.watchtower.yml  # 서버 전용 — 새 이미지 자동교체(무인배포)
  .github/workflows/deploy.yml   # CI/CD: push→테스트→이미지빌드→ghcr.io push
  DEPLOY-LIGHTSAIL.md         # ★ 실제 배포 기록(Lightsail+Tailscale+CI/CD)
  DESIGN-NOTES.md             # ★ 설계 회의 결론(방진시설/모드/패키징)
  backend/
    Dockerfile  requirements.txt   # Dockerfile 은 tossapi/·brokers/·app/ 모두 COPY(필수)
    tossapi/         # 토스 클라이언트 라이브러리 (config/auth/client/errors)
    brokers/         # ★ 증권사 추상화 (Dockerfile COPY 대상 — 빠지면 ModuleNotFound)
      base.py        # Broker ABC
      toss.py        # TossBroker — 토스 (완성)
      kiwoom.py      # KiwoomBroker — 키움 REST (매수전용 봇 필요분 전부 구현)
      __init__.py    # get_broker(): BROKER=toss|kiwoom (.env 먼저 로드)
    app/
      main.py        # FastAPI + CORS + 스케줄러 + 실시간ws lifespan
      deps.py        # get_client()=get_broker(), 에러변환
      routers/       # market, account, orders(취소·조회), bot(+stream SSE)
      bot/           # config, strategy, guardrails, executor, runner, scheduler,
                     # backtest, portfolio, catalog, state, realtime(ws), notify(디코)
    tests/           # pytest 27개
  frontend/
    Dockerfile  nginx.conf
    src/ App.tsx api.ts types.ts App.css
         AutoPage.tsx(메인) PortfolioPanel.tsx HoldingsDonut.tsx
         Chart.tsx OrderbookLadder.tsx RankingPanel.tsx 등
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

## 4. 화면 (현재 = 적립 단일 탭, 브랜드 "autovest")
조회/랭킹/로그 탭은 코드는 남기되 숨김(App.tsx 주석). 적립 탭 흐름(AutoPage.tsx):
- **① 지금 내 자산**: 보유 도넛(HoldingsDonut) + **보유 종목 수익률 표**(종목·수량·평균가·현재가·평가금액·손익·수익률, 실계좌)
- **② 목표 비중**: PortfolioPanel — 비중추종. 목표까지 N%p 부족/초과 뱃지 + ⬅ 다음 적립, 살수있는거라도산다│기다린다 토글
- **③ 전략 상태**: DRY/LIVE·킬스위치 · 스케줄러 heartbeat · **실시간 체결통보 연결 배지** · **누적투입/보유수량(실계좌 기준)** · 다음 적립 미리보기(NextBuy, 현재가 포함) · 상세설정
- **④ 실행 기록**: 봇 실행 로그(체결/미체결 글자) + **대기 중 주문(취소 버튼)** + **거래내역(실제 체결, 다일자)**
- 첫 로딩 스켈레톤, 상단 브로커 토글(토스│키움), 모두 브로커별 분리.
- **실시간**: `/api/bot/stream`(SSE) 구독 → 체결 시 즉시 갱신 + 🔔 토스트.

## 5. 브로커 구현 현황 (키움 매수전용 통합 = 완료)
토스: **전부 구현·동작.** 키움(REST, `BROKER=kiwoom`): 매수전용 적립봇에 필요한 건 **전부 구현·동작.**
응답을 **토스 형태로 정규화**하는 게 핵심.

| 기능 | 토스 | 키움 TR | 키움 상태 |
|---|---|---|---|
| 토큰 | OAuth2 | au10001 | ✅ |
| 계좌 | ✅ | ka00001 | ✅ (`acctNo`) |
| 호가 | ✅ | ka10004 | ✅ (10단계, sel_fpr/sel_Nth, buy_fpr/buy_Nth) |
| 현재가 | ✅ | ka10006 | ✅ (`close_pric`, 부호제거) |
| 보유/잔고 | ✅ | kt00018 | ✅ (`acnt_evlt_remn_indv_tot`, 0패딩·% 변환) |
| 일봉차트 | ✅ | ka10081 | ✅ |
| 매수가능금액 | ✅ | ka00001 (예수금) | ✅ (`cashBuyingPower`) |
| 종목정보(이름) | ✅ | get_stocks | ✅ |
| 매수 주문 | ✅(클라) | kt10000 | ✅ (매수전용, trde_tp 0=지정/3=시장) |
| 미체결 조회 | ✅ | ka10075 | ✅ (PENDING) |
| **체결 확인** | ✅ | ka10076 | ✅ (체결가·수량·평단 → 비중추종 갱신) |
| **주문 취소** | ✅(클라) | kt10003 | ✅ (미체결 잔량 취소, `/api/orders/{id}/cancel`) |
| **거래내역(다일자)** | ✅ | kt00007 | ✅ (최근 14영업일 날짜순회+연속조회, 429 백오프/캐시) |
| **실시간 체결통보** | — | WebSocket | ✅ (wss LOGIN→REG 00→REAL → SSE·디코알림) |
| 매도/정정/체결내역상세/상하한가/수수료 | ✅(클라) | — | ⬜ 매수전용 봇엔 불필요(미구현) |

키움 시각 정규화: HHMMSS/YYYYMMDDHHMMSS → ISO-8601(KST) `_ts_iso()` (토스 orderedAt 과 통일).
실시간 ws: `KiwoomBroker.ws_url()`/`access_token()`. 접속 `wss://api.kiwoom.com:10000/api/dostk/websocket`.

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
- **Dockerfile 이 `brokers/` COPY 빠지면** 컨테이너에서 `No module named 'brokers'` 로 죽음(겪음, 수정됨).
- **디스코드 웹훅은 User-Agent 헤더 없으면 403** — notify.py 에 넣음.
- **containrrr/watchtower 구버전**이 도커 API 1.25 로 붙어 최신 데몬이 거부 → `DOCKER_API_VERSION=1.44` env 로 해결.
- **kiwoom 거래내역(kt00007)은 하루 단위** — 빈 ord_dt=오늘만. 전체는 날짜 순회(14영업일) + 연속조회, 429 백오프·10초 캐시.
- **틱(호가단위)은 고정 5원**(ETF 균일). 소켓 아님. 일반주식 가변틱은 미대응(ETF 봇이라 무관).
- **③ 누적투입/보유수량은 실계좌 기준**(holdings 매입금액 합). state 자체장부는 갓 배포 시 0이라 화면엔 안 씀.
- **완전 균형 시에도 적립**: portfolio.select_underweight 가 deficit>0 없으면 전체를 후보로(현금 안 놀림).
- **스케줄러가 브로커 하나 실패하면 나머지도 스킵되던 버그**: `_loop()`이 틱 전체를 감싸는 try/except 하나만 썼는데, `available_brokers()`가 toss→kiwoom 순으로 순회하다 toss 처리 중 예외가 나면 kiwoom 은 그 틱에서 아예 시도도 안 됐음(lastFiredAt 계속 비어있던 원인). **브로커별 개별 try/except로 격리**해 해결. 실패 사유는 `_last_error`에 담겨 `/api/bot/scheduler`의 `lastError`로 노출됨(진단용).
- **주문 실패가 실행기록에 안 남던 버그**: `executor.execute`가 `TossApiError`만 catch했는데, 키움은 주문 거부를 `RuntimeError`로 던짐(`kiwoom.py`의 `_request()`가 `return_code!=0`이면 RuntimeError). 안 잡혀서 위로 새다가 scheduler의 try/except에서만 조용히 삼켜져 대시보드엔 전혀 안 보였음. **RuntimeError도 잡아서 SKIP 로그로 정상 기록**하도록 수정.
- **하루 1회 → 하루 예산 소진까지 여러 번**: `state.today_budget_used_krw`/`today_budget_date`로 "오늘 남은 한도"를 추적. `guardrails.check()`의 하루1회 게이트(`already_traded_today`)는 완전 제거. 스케줄러는 09:05 단발 대신 **장중(09:05~15:20) 10분 간격으로 반복 체크**(`scheduler._should_check`) — 예산 남았거나 입금 들어오거나 가격 내려가면 다음 체크에서 자동으로 이어서 삼.
- **⚠️ 미해결: 시장가 매수 "매수증거금 부족" 거부** — 실사례: 매수가능금액(예수금 기준, kt00001) 73,490원 있는데 2주(60,270원, 여유충분해 보임) 시장가 주문이 거부됨("1주 매수가능"). **키움앱에서도 주문가능현금 동일하게 73,490원으로 확인됨 — 계좌 문제 아님.**
  - 가설: 시장가는 체결가가 상한가(+30%)까지 튈 수 있어 증권사가 상한가 기준으로 증거금을 미리 잡음. `가격×1.3`로 나눠 수량 계산하면 실사례 결과("1주만 가능")와 정확히 일치하긴 함 — **근데 이 30%는 공식 문서로 확인한 값이 아니라 추측(KRX 가격제한폭 30%에서 역산)이라 확신 없음.**
  - `kt00010`(주문인출가능금액요청)의 `profa_100ord_alowq`로 실제 가능수량을 재확인하는 시도를 했었으나, **정상 매수까지 막는 부작용**이 있어서 되돌림(그 필드가 신용/미수 거래 맥락일 가능성 — "100"이 "100% 현금"이 아니라 다른 의미로 추정). `KiwoomBroker.get_order_affordable_qty` 는 제거됨.
  - 지금 배포된 상태: `portfolio.py`의 `_MARKET_ORDER_MARGIN_BUFFER = 1.3` 로 수량을 보수적으로 계산 중(추측값 그대로 사용 중). **부작용**: 버퍼가 실제보다 작게 쪼개 계산해서, 한 번에 살 수 있었을 수량이 여러 번의 1주 매수로 나뉘어 나감(같은 실행 안에서 그리디 루프가 반복되며 발생). 사용자가 "이거 버그 아니냐" 지적함 — 수학적으로 모순은 아니지만(2주 필요 증거금이 43,355~73,490 사이 어딘가라면 앞뒤 안 맞진 않음) 실용적으론 비효율적(주문 쪼개짐).
  - **다음 세션에서 결정할 것**: 시장가+추측버퍼 대신 **"현재가+소폭 프리미엄(예 0.5%) 지정가"**로 바꾸는 안 논의됨(사용자가 제안) — 지정가는 상한가 버퍼가 필요 없어 자금을 정확하게 쓸 수 있고, 프리미엄으로 즉시체결도 노릴 수 있음. `round_up_to_tick` 헬퍼까지 설계했었으나 **사용자가 "의사결정 확정 없이 코드부터 고치지 말라"고 중단시켜 커밋 전 되돌림(미반영)**. 진행하려면 먼저 사용자 확정 받을 것.
- **오늘 예산 소진 시 API 호출 낭비**: 장중 10분 체크가 "오늘 남은 한도 0원"이어도 보유현황·종목별 가격 조회(API 호출)를 다 하고 나서야 SKIP 처리하고 있었음. `state.today_remaining_budget()`은 cfg/state 만으로 계산 가능(API 불필요)하므로, 이 체크를 `run_once()` 맨 앞으로 옮겨 0이면 나머지 API 호출을 생략하고 즉시 종료하도록 수정(레이트리밋 부담 감소). cfg 는 매번 파일에서 새로 읽으므로(캐시 없음), 장중에 하루 한도를 올리면 다음 체크에서 바로 반영됨(확인됨).
- **SKIP 로그에 069500(KODEX 200)이 잘못 찍히던 버그**: `executor.execute()`가 `sym = d.symbol or cfg.symbol` 를 SKIP 여부와 무관하게 먼저 계산했음. `runner._skip()`이 `Decision(..., symbol="")`으로 빈 문자열을 넘기는데, `""`는 falsy라 `cfg.symbol`(레거시 단일종목 기본값 `069500`=KODEX 200)로 폴백됨. 그래서 "오늘 살 게 없음"/"현금 부족" 같은 SKIP 사유 로그마다 symbol 칸에 069500이 찍혀 **실제로 매수 시도한 적 없는데도 매수 시도처럼 보임**(사용자가 "포폴에 있지도 않은 069500을 왜 사려하냐"고 지적해서 발견). 실주문은 전혀 안 나갔음(SKIP은 `create_order` 호출 자체가 없음) — 순수 표시 버그. **수정**: SKIP일 땐 `cfg.symbol` 폴백 없이 `d.symbol or None` 그대로 기록(`OrderLog.symbol` 타입도 `str | None`로 변경). 프론트는 `lg.symbol ?? '-'`라 화면엔 `-`로 뜸.
- **일부 종목 시세조회 실패 → "이미 목표비중 도달"로 오인**: `_portfolio_prices()`가 종목별 현재가 조회 실패 시 조용히 `continue`(해당 종목만 `prices` dict에서 빠짐). `plan_daily_buys()`는 `prices`에 없는 종목을 후보에서 통째로 제외하는데, 이걸 "진짜 균형(살 게 없음)"과 구분을 안 해서, 나스닥100 하나만 시세조회 실패해도 "오늘 살 게 없음 — 이미 목표 비중 도달"로 잘못 표시됨(실제론 그 종목만 계산에서 빠진 것). **수정**: `_missing_price_symbols()` 추가해 cfg.portfolio엔 있는데 이번 tick의 `prices`엔 없는 종목을 따로 판정 → "시세 조회 실패: {symbol} — 다음 확인 때 재시도"로 명확히 표시. 이 경우엔 `cash_exhausted_date` 억제도 안 걸어서 다음 10분 tick에 바로 재시도됨.
- **예산은 남았는데 1주도 못 사는 경우도 "이미 목표비중 도달"로 오인**: `budget <= 0`만 "예산부족"으로 판정했는데, 실제로는 `budget > 0`이지만 부족 종목 1주 값(증거금버퍼 1.3배 포함)보다 적은 경우도 있음(예: 나스닥100이 명백히 부족한데 예산이 그 1주 값보다 작음). 이때도 `plan_daily_buys`가 빈 리스트를 반환해 "균형 상태"와 똑같이 취급됐음. **수정**: `portfolio.has_underweight_target(cfg, current_values, prices)` 추가 — "진짜 균형" vs "예산만 부족"을 구분. 후자면 "목표비중 미달 종목이 있지만 예산 부족으로 1주도 못 삽니다 — 입금이 필요합니다"로 표시(cash_exhausted_date 억제도 걸어 스팸 방지).
  - **⚠️ 최초 구현이 잘못됐었음(같은 세션에서 바로 발견·재수정)**: `has_underweight_target`을 처음엔 `plan_daily_buys(budget=10**15, max_iters=1)`가 뭔가 반환하는지로 판정했는데, `plan_daily_buys`엔 "완전 균형이어도 현금 안 놀리려고 1주씩 계속 산다"는 폴백(§ "완전 균형 시에도 적립" 참고)이 있어서, 예산을 무한대로 주면 균형 여부와 무관하게 **항상 뭔가를 사버려 늘 `True`**가 나옴(완벽히 60:40인 포트폴리오로 직접 테스트해서 확인). 즉 "이미 목표비중 도달" 분기가 사실상 죽은 코드가 될 뻔함. **재수정**: `plan_daily_buys` 호출 없이, 그 폴백 로직을 뺀 순수 `ideal_needed`(목표비중까지 필요한 금액) 부호만으로 직접 판정하도록 재작성. 콜드스타트(총 투자금 0원)는 이 공식이 자연히 0을 내어 "균형"으로 오인될 수 있어 `total_v<=0`이면 명시적으로 "부족함(True)" 처리 추가.

## 7. 보안 / 법적 (사용자와 논의됨)
- 키는 `.env`에만(절대 채팅·git 금지). **채팅에 한번 노출된 키는 운영 전 재발급 권장.**
- 서비스화: **각자 자기 키로 자기 환경에서 실행(오픈소스 셀프호스팅)** 이 법적으로 안전. 호스팅+대신매매=투자일임업 규제. UI만 호스팅+IP입력은 HTTPS 혼합콘텐츠로 막힘 → docker 번들 또는 데스크탑앱이 답.
- 배포는 Oracle Cloud **Always Free**(영구무료 ARM) 또는 EC2/Lightsail. 접근은 SSH터널/Tailscale/방화벽(내IP만)으로 — 트레이딩 대시보드라 전체공개 금지.

## 8. 현황 / 다음 할 일
**프로덕션 배포·무인 CI/CD·실시간·알림까지 완료.** (2026-07-01 기준)

배포(상세 = `DEPLOY-LIGHTSAIL.md`):
- **AWS Lightsail(서울, Ubuntu 24.04, 1GB) 상시 가동.** 토스+키움 둘 다 인증(양쪽 서버IP 등록).
- 접근: **Tailscale serve HTTPS** `https://ip-172-26-7-8.<tailnet>.ts.net/` (내 기기만). 8080 미개방 + 127.0.0.1 바인딩 = 이중 차단.
- **CI/CD 무인 배포**: `git push` → Actions(pytest+tsc→이미지빌드→ghcr.io) → 서버 Watchtower 자동교체. ghcr 패키지는 public(서버 무자격 pull). bot_data 볼륨로 상태 유지.
- **디스코드 알림**: 실시간 체결 시 "🟢 체결 …"(키움 LIVE만). 서버 `.env`에 `DISCORD_WEBHOOK_URL` 넣어야 동작.

이전 세션 추가 기능: 주문취소(kt10003)·거래내역(kt00007)·실시간 체결통보(ws→SSE)·디코알림·
보유종목 수익률표·수동재적립 가드우회·균형시에도 적립·시각포맷 통일·실계좌 기준 누적투입.

**이번 세션(2026-07-06, 실거래 LIVE 운영 중 발견된 버그들)**:
- 그리디 다중종목 리밸런싱 적립 완성(`portfolio.plan_daily_buys`) — 하루 예산을
  오버슈팅 없이 여러 ETF에 그리디 분배, 시장가로 순차 실행.
- 스케줄러 브로커별 예외격리 버그 수정 (§6 참고, 실거래 중 발견 — kiwoom 이 계속
  안 사던 원인이었음).
- executor 가 RuntimeError 를 안 잡아 실행기록에 실패사유가 안 남던 버그 수정.
- "하루 1회" → "하루 예산 소진까지 장중 10분 간격 반복" 으로 아키텍처 전환.
- 자산 실시간화(키움 04 현물잔고 + 0B 주식체결 구독), 롤링 숫자 애니메이션,
  자산 가리기(기본 ON)+재미 인플레이션(0 3개), PWA, 반응형, 장운영 배지 등.
- **⚠️ 시장가 매수 "매수증거금 부족" 이슈 미해결** — §6 참고. 임시로 추측 버퍼(1.3배)
  적용 중인데 부작용(주문 쪼개짐)이 있어 사용자가 "지정가+프리미엄" 대안을
  제안했으나 **구현 전 중단됨(코드 되돌림)**. 다음 세션 최우선 안건.

**이번 세션(2026-07-08, 실행기록 SKIP 사유 오표시 3건 수정)**:
- 사용자가 대시보드에서 "나스닥100이 명백히 부족한데 왜 목표비중 도달이라 뜨냐",
  "포폴에 없는 069500(KODEX 200)을 왜 사려하냐" 지적 → 조사 결과 실제 매수 로직
  버그가 아니라 **SKIP 사유 판정/표시 로직의 정밀도 부족**이 원인이었음(§6 참고):
  1. SKIP 로그 symbol 필드가 `cfg.symbol`(레거시 기본값 069500)로 잘못 폴백되던 버그.
  2. 시세조회 실패 종목이 "균형 상태"로 오인되던 버그.
  3. 예산은 남았지만 1주도 못 사는 상태가 "균형 상태"로 오인되던 버그.
- 세 건 모두 수정·테스트(39개 통과)·커밋·푸시 완료, Watchtower 자동배포 트리거됨.
- 실행기록 탭이 계속 길어지는 문제 → 20개씩 페이징(이전/다음) 추가.

남은 일(우선순위):
1. **[최우선] 시장가 증거금 버퍼 문제 해결** — "지정가(현재가+0.5%)+올림틱" 방식으로
   전환할지 사용자와 먼저 확정 후 진행. §6 참고, `round_up_to_tick` 설계는 돼있었음.
2. **DRY→LIVE 운영 안정화** — 이미 LIVE 로 실거래 중(2026-07-06 기준). 버퍼 이슈로
   실제 매수가 계획보다 적게/쪼개져서 나가고 있어 위 1번과 직결.
3. (설계보류) "방진 모드"(공개 전략repo + B-pull 봉인) — `DESIGN-NOTES.md` 참고, 지금은 심플 모드.
4. (면접 대비) README 를 차별점(비중 리밸런싱 적립)·아키텍처·안전장치 중심으로 재정리.
5. (보너스) 키움 순위정보/기관외국인 → 진짜 랭킹·수급.

## 9. 사용자 정보
- 소액 실거래로 검증할 계획(키움 모의투자는 안 씀 → 주문 테스트는 진짜 돈, 1주 소액 필수).
- 토스 종합계좌(13501006210), 키움 계좌(6674517110) 둘 다 현금 거의 0.
- 봇은 기본 DRY_RUN 유지 권장. LIVE 전환은 사용자가 직접.

## 10. 작업 방식 (사용자 선호)
- 변경 후 **타입체크(tsc)·테스트·헤드리스 크롬 스크린샷으로 자가검증** 후 보고. (Chrome: `--headless=new --screenshot`)
- 키움 TR은 사용자가 명세(요청/응답 예시) 주면 정규화 구현. **api-id 모르면 후보를 직접 호출해 탐색**(읽기 TR은 안전).
- 명세 없이 필드명 지어내지 말 것(환각 → 틀린 주문 위험).
- **실제로 이 규칙을 어겨서 문제가 됐던 사례**: kt00010 응답의 `profa_100ord_alowq`를
  "100=현금(무증거금) 기준 실제 주문가능수량"이라고 넘겨짚고 주문 직전 클램프에
  썼다가, 정상적으로 매수되던 계좌의 주문까지 막아버림(그 필드가 신용/미수 거래
  맥락일 가능성 — 확인 안 된 채 썼다가 실거래에 부작용 냄). **명세에 필드명은 있어도
  "정확히 어떤 상황에 적용되는 값인지"까지 확실하지 않으면, 실거래에 바로 쓰지 말고
  먼저 물어보거나 소액으로 검증할 것.** 코드 수정 자체도 사용자 확정 없이 먼저
  진행했다가 되돌리는 일이 있었음 — **의사결정이 필요한 변경은 반드시 먼저 확인받고
  코드 작성.
- **커밋 메시지에 AI 에이전트 흔적을 남기지 말 것.** `Co-Authored-By: Claude ...` 또는 유사한 AI 공동저자 태그를 커밋 메시지에 절대 포함하지 않는다. 커밋은 사용자 단독 저작으로 기록한다.**
