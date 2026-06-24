"""토스증권 Open API REST 클라이언트.

모든 엔드포인트를 메서드로 감싸고, 공통 응답 envelope(`result`)/에러(`error`)를
일관되게 처리한다. 401(토큰 만료) 자동 재발급, 429(rate limit) 재시도 포함.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import requests

from .auth import TokenManager
from .config import Settings, load_settings
from .errors import RateLimitError, TossApiError, TossAuthError

_MAX_RETRIES = 3


class TossClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ):
        self.settings = settings or load_settings()
        self._session = session or requests.Session()
        self._timeout = timeout
        self._tokens = TokenManager(
            self.settings.client_id,
            self.settings.client_secret,
            self.settings.base_url,
            session=self._session,
            timeout=timeout,
        )
        # 계좌 컨텍스트가 필요한 호출용. 미설정 시 첫 계좌를 lazy 로 채운다.
        self._account_seq: int | None = self.settings.account_seq

    # ------------------------------------------------------------------ #
    # 공통 요청 처리
    # ------------------------------------------------------------------ #
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any | None = None,
        account_seq: int | None = None,
        auth: bool = True,
    ) -> Any:
        url = f"{self.settings.base_url}{path}"
        params = _clean(params)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            headers: dict[str, str] = {}
            if auth:
                headers["Authorization"] = f"Bearer {self._tokens.get_token()}"
            if account_seq is not None:
                headers["X-Tossinvest-Account"] = str(account_seq)

            try:
                resp = self._session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(0.5 * (attempt + 1))
                continue

            # 토큰 만료 -> 강제 재발급 후 1회 재시도
            if resp.status_code == 401 and auth and attempt == 0:
                self._tokens.get_token(force_refresh=True)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "1") or 1)
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(retry_after)
                    continue
                raise _build_error(resp, rate_limit=True, retry_after=retry_after)

            if resp.status_code >= 400:
                raise _build_error(resp)

            return _unwrap(resp)

        raise TossApiError(0, code="network-error", message=str(last_exc))

    def _ensure_account(self, account_seq: int | None) -> int:
        seq = account_seq if account_seq is not None else self._account_seq
        if seq is None:
            accounts = self.get_accounts()
            if not accounts:
                raise TossApiError(0, code="no-account", message="사용 가능한 계좌가 없습니다.")
            seq = int(accounts[0]["accountSeq"])
            self._account_seq = seq
        return seq

    # ================================================================== #
    # Market Data (시세) — 계좌 불필요
    # ================================================================== #
    def get_orderbook(self, symbol: str) -> dict:
        """호가 조회."""
        return self._request("GET", "/api/v1/orderbook", params={"symbol": symbol})

    def get_prices(self, symbols: str | Iterable[str]) -> list[dict]:
        """현재가 조회. 최대 200건 다건."""
        return self._request("GET", "/api/v1/prices", params={"symbols": _join(symbols)})

    def get_price(self, symbol: str) -> dict | None:
        """단건 현재가 헬퍼."""
        result = self.get_prices(symbol)
        return result[0] if result else None

    def get_trades(self, symbol: str, count: int = 50) -> list[dict]:
        """최근 체결 내역 (최대 50)."""
        return self._request(
            "GET", "/api/v1/trades", params={"symbol": symbol, "count": count}
        )

    def get_price_limits(self, symbol: str) -> dict:
        """상/하한가 조회."""
        return self._request("GET", "/api/v1/price-limits", params={"symbol": symbol})

    def get_candles(
        self,
        symbol: str,
        interval: str = "1d",
        count: int = 100,
        before: str | None = None,
        adjusted: bool = True,
    ) -> dict:
        """캔들(OHLCV) 조회. interval: '1m' | '1d'. 최대 200봉."""
        return self._request(
            "GET",
            "/api/v1/candles",
            params={
                "symbol": symbol,
                "interval": interval,
                "count": count,
                "before": before,
                "adjusted": str(adjusted).lower(),
            },
        )

    # ================================================================== #
    # Stock Info / Market Info — 계좌 불필요
    # ================================================================== #
    def get_stocks(self, symbols: str | Iterable[str]) -> list[dict]:
        """종목 기본 정보. 최대 200건 다건."""
        return self._request("GET", "/api/v1/stocks", params={"symbols": _join(symbols)})

    def get_stock_warnings(self, symbol: str) -> list[dict]:
        """매수 유의사항 / VI 발동 조회."""
        return self._request("GET", f"/api/v1/stocks/{symbol}/warnings")

    def get_exchange_rate(
        self, base_currency: str = "USD", quote_currency: str = "KRW", date_time: str | None = None
    ) -> dict:
        """환율 조회."""
        return self._request(
            "GET",
            "/api/v1/exchange-rate",
            params={
                "baseCurrency": base_currency,
                "quoteCurrency": quote_currency,
                "dateTime": date_time,
            },
        )

    def get_kr_market_calendar(self, date: str | None = None) -> dict:
        """국내 장 운영 정보."""
        return self._request("GET", "/api/v1/market-calendar/KR", params={"date": date})

    def get_us_market_calendar(self, date: str | None = None) -> dict:
        """해외(미국) 장 운영 정보."""
        return self._request("GET", "/api/v1/market-calendar/US", params={"date": date})

    # ================================================================== #
    # Account / Asset
    # ================================================================== #
    def get_accounts(self) -> list[dict]:
        """계좌 목록 조회. accountSeq 진입점."""
        return self._request("GET", "/api/v1/accounts")

    def get_holdings(self, symbol: str | None = None, account_seq: int | None = None) -> dict:
        """보유 주식 조회."""
        seq = self._ensure_account(account_seq)
        return self._request(
            "GET", "/api/v1/holdings", params={"symbol": symbol}, account_seq=seq
        )

    # ================================================================== #
    # Order Info (주문 전 확인)
    # ================================================================== #
    def get_buying_power(self, currency: str = "KRW", account_seq: int | None = None) -> dict:
        """매수 가능 금액 조회."""
        seq = self._ensure_account(account_seq)
        return self._request(
            "GET", "/api/v1/buying-power", params={"currency": currency}, account_seq=seq
        )

    def get_sellable_quantity(self, symbol: str, account_seq: int | None = None) -> dict:
        """판매 가능 수량 조회."""
        seq = self._ensure_account(account_seq)
        return self._request(
            "GET", "/api/v1/sellable-quantity", params={"symbol": symbol}, account_seq=seq
        )

    def get_commissions(self, account_seq: int | None = None) -> list[dict]:
        """매매 수수료 조회."""
        seq = self._ensure_account(account_seq)
        return self._request("GET", "/api/v1/commissions", account_seq=seq)

    # ================================================================== #
    # Order History (주문 조회)
    # ================================================================== #
    def get_orders(
        self,
        status: str = "OPEN",
        symbol: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
        account_seq: int | None = None,
    ) -> dict:
        """주문 목록. status: 'OPEN' | 'CLOSED'."""
        seq = self._ensure_account(account_seq)
        return self._request(
            "GET",
            "/api/v1/orders",
            params={
                "status": status,
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
                "cursor": cursor,
                "limit": limit,
            },
            account_seq=seq,
        )

    def get_order(self, order_id: str, account_seq: int | None = None) -> dict:
        """주문 상세 조회."""
        seq = self._ensure_account(account_seq)
        return self._request("GET", f"/api/v1/orders/{order_id}", account_seq=seq)

    # ================================================================== #
    # Order (실제 매매) — 주의: 계좌에 직접 영향
    # ================================================================== #
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "LIMIT",
        *,
        quantity: str | int | None = None,
        price: str | int | float | None = None,
        order_amount: str | float | None = None,
        time_in_force: str | None = None,
        client_order_id: str | None = None,
        confirm_high_value_order: bool = False,
        account_seq: int | None = None,
    ) -> dict:
        """주문 생성.

        side: 'BUY' | 'SELL', order_type: 'LIMIT' | 'MARKET'.
        quantity(수량) 또는 order_amount(US MARKET 금액) 중 정확히 하나.
        """
        seq = self._ensure_account(account_seq)
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
        }
        if quantity is not None:
            body["quantity"] = str(quantity)
        if order_amount is not None:
            body["orderAmount"] = str(order_amount)
        if price is not None:
            body["price"] = str(price)
        if time_in_force is not None:
            body["timeInForce"] = time_in_force
        if client_order_id is not None:
            body["clientOrderId"] = client_order_id
        if confirm_high_value_order:
            body["confirmHighValueOrder"] = True
        return self._request("POST", "/api/v1/orders", json=body, account_seq=seq)

    def modify_order(
        self,
        order_id: str,
        order_type: str = "LIMIT",
        *,
        price: str | int | float | None = None,
        quantity: str | int | None = None,
        confirm_high_value_order: bool = False,
        account_seq: int | None = None,
    ) -> dict:
        """주문 정정. KR: quantity 필수, US: price 만."""
        seq = self._ensure_account(account_seq)
        body: dict[str, Any] = {"orderType": order_type}
        if price is not None:
            body["price"] = str(price)
        if quantity is not None:
            body["quantity"] = str(quantity)
        if confirm_high_value_order:
            body["confirmHighValueOrder"] = True
        return self._request(
            "POST", f"/api/v1/orders/{order_id}/modify", json=body, account_seq=seq
        )

    def cancel_order(self, order_id: str, account_seq: int | None = None) -> dict:
        """주문 취소."""
        seq = self._ensure_account(account_seq)
        return self._request(
            "POST", f"/api/v1/orders/{order_id}/cancel", json={}, account_seq=seq
        )


# ---------------------------------------------------------------------- #
# 헬퍼
# ---------------------------------------------------------------------- #
def _join(symbols: str | Iterable[str]) -> str:
    if isinstance(symbols, str):
        return symbols
    return ",".join(symbols)


def _clean(params: dict | None) -> dict | None:
    """None 값 파라미터 제거."""
    if not params:
        return params
    return {k: v for k, v in params.items() if v is not None}


def _unwrap(resp: requests.Response) -> Any:
    """성공 응답 envelope 에서 result 를 꺼낸다."""
    if not resp.content:
        return None
    body = resp.json()
    if isinstance(body, dict) and "result" in body:
        return body["result"]
    return body


def _build_error(
    resp: requests.Response, *, rate_limit: bool = False, retry_after: float | None = None
) -> TossApiError:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    err = body.get("error", {}) if isinstance(body, dict) else {}
    kwargs = dict(
        status_code=resp.status_code,
        code=err.get("code"),
        message=err.get("message") or resp.text[:200],
        request_id=err.get("requestId") or resp.headers.get("X-Request-Id"),
        data=err.get("data"),
    )
    if rate_limit:
        return RateLimitError(retry_after=retry_after, **kwargs)
    if resp.status_code == 401:
        return TossAuthError(**kwargs)
    return TossApiError(**kwargs)
