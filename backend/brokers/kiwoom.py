"""키움증권 REST API 브로커 (골격).

⚠️ 실제 엔드포인트·요청/응답 필드는 키움 OpenAPI(REST) 공식 명세를 받아 채운다.
지금은 인터페이스만 맞춰둔 골격이며, 호출 시 NotImplementedError 를 던진다.

구현 시 채울 것:
- 인증: appkey/secretkey -> 접근토큰 (모의/실전 서버 URL 구분)
- 각 메서드: 키움 REST 엔드포인트 호출 후, 응답을 토스와 동일한 dict 형태로 정규화
  (봇·UI 가 동일 구조를 기대하므로 '응답 변환'이 핵심 작업)
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta

import requests

from typing import Any, Iterable

from .base import Broker

_TODO = "키움 REST 명세를 받아 구현 필요"

_LIVE = "https://api.kiwoom.com"
_MOCK = "https://mockapi.kiwoom.com"


class KiwoomBroker(Broker):
    """키움증권 REST API 브로커.

    인증(au10001)은 구현 완료. 시세/계좌/주문 메서드는 각 TR 명세를 받아 채운다.
    """

    def __init__(self, app_key: str | None = None, secret_key: str | None = None,
                 paper: bool | None = None, timeout: float = 10.0):
        self.app_key = app_key or os.getenv("KIWOOM_APP_KEY", "").strip()
        self.secret_key = secret_key or os.getenv("KIWOOM_SECRET_KEY", "").strip()
        # paper=True 면 모의투자 서버(KRX만). 기본은 env KIWOOM_PAPER, 없으면 실전
        if paper is None:
            paper = os.getenv("KIWOOM_PAPER", "false").strip().lower() == "true"
        self.base_url = _MOCK if paper else _LIVE
        self._timeout = timeout
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_exp: datetime | None = None

    # ---------------- 인증 (au10001) ----------------
    def _get_token(self, force: bool = False) -> str:
        with self._lock:
            if not force and self._token and self._token_exp \
                    and datetime.now() < self._token_exp - timedelta(minutes=5):
                return self._token
            if not self.app_key or not self.secret_key:
                raise RuntimeError("KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 가 설정되지 않았습니다.")
            resp = self._session.post(
                f"{self.base_url}/oauth2/token",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "secretkey": self.secret_key,
                },
                headers={"Content-Type": "application/json;charset=UTF-8"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            # 키움은 실패해도 HTTP 200 + return_code != 0 으로 응답한다
            if body.get("return_code") not in (0, None) or "token" not in body:
                raise RuntimeError(
                    f"키움 토큰 발급 실패 (code={body.get('return_code')}): "
                    f"{body.get('return_msg', body)}"
                )
            self._token = body["token"]
            self._token_exp = _parse_expiry(body.get("expires_dt"))
            return self._token

    # ---------------- 공통 요청 ----------------
    def _request(self, api_id: str, path: str, body: dict | None = None,
                 cont_yn: str | None = None, next_key: str | None = None) -> dict:
        """키움 REST 공통 POST. 헤더에 authorization + api-id(TR), 본문은 JSON.
        실패해도 HTTP 200 + return_code!=0 으로 오므로 그것도 검사한다."""
        headers = {
            "authorization": f"Bearer {self._get_token()}",
            "api-id": api_id,
            "Content-Type": "application/json;charset=UTF-8",
        }
        if cont_yn:
            headers["cont-yn"] = cont_yn
        if next_key:
            headers["next-key"] = next_key
        resp = self._session.post(
            f"{self.base_url}{path}", json=body or {}, headers=headers, timeout=self._timeout
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("return_code") not in (0, None):
            raise RuntimeError(
                f"키움 {api_id} 실패 (code={data.get('return_code')}): {data.get('return_msg', data)}"
            )
        return data

    def get_orderbook(self, symbol: str) -> dict:
        """ka10004 주식호가요청 → 토스 형태({asks, bids})로 정규화.
        매도최우선=sel_fpr(1단계), 2~10단계=sel_Nth. 매수도 동일(buy_fpr, buy_Nth)."""
        data = self._request("ka10004", "/api/dostk/mrkcond", body={"stk_cd": symbol})

        def num(v) -> str:
            s = str(v or "").replace("+", "").replace("-", "").strip()
            return s or "0"

        asks: list[dict] = []
        if data.get("sel_fpr_bid"):
            asks.append({"price": num(data["sel_fpr_bid"]), "volume": num(data.get("sel_fpr_req"))})
        for i in range(2, 11):
            bid = data.get(f"sel_{i}th_pre_bid")
            if bid and num(bid) != "0":
                asks.append({"price": num(bid), "volume": num(data.get(f"sel_{i}th_pre_req"))})

        bids: list[dict] = []
        if data.get("buy_fpr_bid"):
            bids.append({"price": num(data["buy_fpr_bid"]), "volume": num(data.get("buy_fpr_req"))})
        for i in range(2, 11):
            bid = data.get(f"buy_{i}th_pre_bid")
            if bid and num(bid) != "0":
                bids.append({"price": num(bid), "volume": num(data.get(f"buy_{i}th_pre_req"))})

        return {"timestamp": data.get("bid_req_base_tm"), "currency": "KRW", "asks": asks, "bids": bids}
    def get_price(self, symbol: str) -> dict | None:
        """ka10006 주식시분요청 → 토스 PriceResponse 형태로 정규화."""
        data = self._request("ka10006", "/api/dostk/mrkcond", body={"stk_cd": symbol})
        close = data.get("close_pric")
        if close is None or str(close).strip() == "":
            return None
        return {
            "symbol": symbol,
            "timestamp": None,
            "lastPrice": _absnum(close),
            "currency": "KRW",
        }

    def get_prices(self, symbols: str | Iterable[str]) -> list[dict]:
        """다건 현재가. 키움은 단건 TR이라 심볼별로 호출해 합친다."""
        syms = symbols.split(",") if isinstance(symbols, str) else list(symbols)
        out: list[dict] = []
        for s in syms:
            s = s.strip()
            if not s:
                continue
            # 한 종목이 실패(429/일시오류)해도 나머지는 채운다
            try:
                p = self.get_price(s)
            except Exception:
                p = None
            if p:
                out.append(p)
        return out
    def get_trades(self, symbol: str, count: int = 50) -> list[dict]: raise NotImplementedError(_TODO)
    def get_price_limits(self, symbol: str) -> dict: raise NotImplementedError(_TODO)
    def get_candles(self, symbol: str, interval: str = "1d", count: int = 100,
                    before: str | None = None, adjusted: bool = True) -> dict:
        """ka10081 주식일봉차트조회 → 토스 CandlePage({candles:[...]}) 형태로 정규화.
        응답 stk_dt_pole_chart_qry 는 최신→과거 순. 필드:
          dt(YYYYMMDD) open_pric high_pric low_pric cur_prc(종가) trde_qty(거래량).
        interval 은 일봉만 지원(이 TR이 일봉 전용)."""
        if interval != "1d":
            raise NotImplementedError("키움 get_candles 는 일봉(1d)만 지원합니다.")
        # base_dt(필수)= before 가 있으면 그 날짜, 없으면 오늘. YYYYMMDD 로 정규화.
        base_dt = (before or datetime.now().strftime("%Y%m%d")).replace("-", "")[:8]
        data = self._request(
            "ka10081", "/api/dostk/chart",
            body={"stk_cd": symbol, "base_dt": base_dt,
                  "upd_stkpc_tp": "1" if adjusted else "0"},
        )
        rows = data.get("stk_dt_pole_chart_qry", []) or []
        candles = []
        for it in rows[:max(0, count)]:
            dt = str(it.get("dt") or "").strip()
            if len(dt) != 8:
                continue
            candles.append({
                "timestamp": f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}",
                "openPrice": _absnum(it.get("open_pric")),
                "highPrice": _absnum(it.get("high_pric")),
                "lowPrice": _absnum(it.get("low_pric")),
                "closePrice": _absnum(it.get("cur_prc")),
                "volume": _i(it.get("trde_qty")),
            })
        return {"candles": candles}
    def get_stocks(self, symbols: str | Iterable[str]) -> list[dict]: raise NotImplementedError(_TODO)
    def get_exchange_rate(self, base_currency: str = "USD", quote_currency: str = "KRW",
                          date_time: str | None = None) -> dict: raise NotImplementedError(_TODO)
    def get_kr_market_calendar(self, date: str | None = None) -> dict: raise NotImplementedError(_TODO)
    def get_accounts(self) -> list[dict]:
        """ka00001 계좌번호조회. 토스와 동일한 형태로 정규화."""
        data = self._request("ka00001", "/api/dostk/acnt")
        acct = data.get("acctNo")
        if not acct:
            return []
        return [{"accountNo": acct, "accountSeq": acct, "accountType": "BROKERAGE"}]
    def get_holdings(self, symbol: str | None = None, account_seq: int | None = None) -> dict:
        """kt00018 계좌평가잔고내역요청 → 토스 HoldingsOverview 형태로 정규화."""
        data = self._request("kt00018", "/api/dostk/acnt",
                             body={"qry_tp": "1", "dmst_stex_tp": "KRX"})
        items = []
        for it in data.get("acnt_evlt_remn_indv_tot", []) or []:
            code = (it.get("stk_cd") or "").lstrip("A") or it.get("stk_cd", "")
            if symbol and code != symbol:
                continue
            evlt = _i(it.get("evlt_amt"))
            pl = _i(it.get("evltv_prft"))
            items.append({
                "symbol": code,
                "name": it.get("stk_nm", code),
                "marketCountry": "KR",
                "currency": "KRW",
                "quantity": _i(it.get("rmnd_qty")),
                "lastPrice": _i(it.get("cur_prc")),
                "averagePurchasePrice": _i(it.get("pur_pric")),
                "marketValue": {
                    "purchaseAmount": _i(it.get("pur_amt")),
                    "amount": evlt,
                    "amountAfterCost": evlt,
                },
                "profitLoss": {
                    "amount": pl,
                    "amountAfterCost": pl,
                    "rate": _rate(it.get("prft_rt")),
                    "rateAfterCost": _rate(it.get("prft_rt")),
                },
                "dailyProfitLoss": {"amount": "0", "rate": "0"},
                "cost": {"commission": _i(it.get("sum_cmsn")), "tax": _i(it.get("tax"))},
            })

        krw = _i(data.get("tot_evlt_amt"))
        pl_total = _i(data.get("tot_evlt_pl"))
        return {
            "totalPurchaseAmount": {"krw": _i(data.get("tot_pur_amt")), "usd": None},
            "marketValue": {
                "amount": {"krw": krw, "usd": None},
                "amountAfterCost": {"krw": krw, "usd": None},
            },
            "profitLoss": {
                "amount": {"krw": pl_total, "usd": None},
                "amountAfterCost": {"krw": pl_total, "usd": None},
                "rate": _rate(data.get("tot_prft_rt")),
                "rateAfterCost": _rate(data.get("tot_prft_rt")),
            },
            "dailyProfitLoss": {"amount": {"krw": "0", "usd": None}, "rate": "0"},
            "items": items,
        }
    def get_buying_power(self, currency: str = "KRW", account_seq: int | None = None) -> dict:
        """kt00001 예수금상세현황요청 → 토스 BuyingPower 형태.
        ord_alow_amt=주문가능금액(매수가능), pymn_alow_amt=출금가능. (0패딩 문자열)"""
        data = self._request("kt00001", "/api/dostk/acnt", body={"qry_tp": "3"})
        cash = _i(data.get("ord_alow_amt"))
        return {
            "currency": "KRW",
            "cashBuyingPower": cash,
            "orderableAmount": cash,
            "withdrawableAmount": _i(data.get("pymn_alow_amt")),
        }
    def get_sellable_quantity(self, symbol: str, account_seq: int | None = None) -> dict:
        raise NotImplementedError(_TODO)
    def get_commissions(self, account_seq: int | None = None) -> list[dict]: raise NotImplementedError(_TODO)
    def get_orders(self, status: str = "OPEN", symbol: str | None = None, **kwargs: Any) -> dict:
        raise NotImplementedError(_TODO)
    def get_order(self, order_id: str, account_seq: int | None = None) -> dict:
        raise NotImplementedError(_TODO)
    def create_order(self, symbol: str, side: str, order_type: str = "LIMIT", **kwargs: Any) -> dict:
        raise NotImplementedError(_TODO)
    def modify_order(self, order_id: str, order_type: str = "LIMIT", **kwargs: Any) -> dict:
        raise NotImplementedError(_TODO)
    def cancel_order(self, order_id: str, account_seq: int | None = None) -> dict:
        raise NotImplementedError(_TODO)


def _absnum(v) -> str:
    """키움 숫자(부호 포함 문자열)에서 부호 제거한 절대값 문자열."""
    return str(v or "").replace("+", "").replace("-", "").strip() or "0"


def _i(v) -> str:
    """0패딩 정수 문자열 -> 정규 정수 문자열 (부호 유지)."""
    s = str(v or "").strip()
    if not s:
        return "0"
    try:
        return str(int(s))
    except ValueError:
        return _absnum(s)


def _rate(v) -> str:
    """키움 수익률(%) -> 토스 소수비율 문자열 (46.25 -> 0.4625)."""
    s = str(v or "").strip()
    if not s:
        return "0"
    try:
        return str(float(s) / 100)
    except ValueError:
        return "0"


def _parse_expiry(s: str | None) -> datetime | None:
    """만료일 문자열 파싱. 형식 미상이면 보수적으로 12시간 뒤로 처리."""
    if not s:
        return datetime.now() + timedelta(hours=12)
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now() + timedelta(hours=12)
