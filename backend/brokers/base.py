"""증권사 공통 인터페이스.

봇·전략·라우터는 이 인터페이스에만 의존한다. 구현체(toss/kiwoom)는 갈아끼운다.
메서드 시그니처는 현재 TossClient 와 동일하게 맞춘다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class Broker(ABC):
    # ---------------- 시세 ----------------
    @abstractmethod
    def get_orderbook(self, symbol: str) -> dict: ...

    @abstractmethod
    def get_prices(self, symbols: str | Iterable[str]) -> list[dict]: ...

    @abstractmethod
    def get_price(self, symbol: str) -> dict | None: ...

    @abstractmethod
    def get_trades(self, symbol: str, count: int = 50) -> list[dict]: ...

    @abstractmethod
    def get_price_limits(self, symbol: str) -> dict: ...

    @abstractmethod
    def get_candles(self, symbol: str, interval: str = "1d", count: int = 100,
                    before: str | None = None, adjusted: bool = True) -> dict: ...

    # ---------------- 종목/시장 정보 ----------------
    @abstractmethod
    def get_stocks(self, symbols: str | Iterable[str]) -> list[dict]: ...

    @abstractmethod
    def get_exchange_rate(self, base_currency: str = "USD", quote_currency: str = "KRW",
                          date_time: str | None = None) -> dict: ...

    @abstractmethod
    def get_kr_market_calendar(self, date: str | None = None) -> dict: ...

    # ---------------- 계좌/자산 ----------------
    @abstractmethod
    def get_accounts(self) -> list[dict]: ...

    @abstractmethod
    def get_holdings(self, symbol: str | None = None, account_seq: int | None = None) -> dict: ...

    @abstractmethod
    def get_buying_power(self, currency: str = "KRW", account_seq: int | None = None) -> dict: ...

    @abstractmethod
    def get_sellable_quantity(self, symbol: str, account_seq: int | None = None) -> dict: ...

    @abstractmethod
    def get_commissions(self, account_seq: int | None = None) -> list[dict]: ...

    # ---------------- 주문 ----------------
    @abstractmethod
    def get_orders(self, status: str = "OPEN", symbol: str | None = None,
                   **kwargs: Any) -> dict: ...

    @abstractmethod
    def get_order(self, order_id: str, account_seq: int | None = None) -> dict: ...

    @abstractmethod
    def create_order(self, symbol: str, side: str, order_type: str = "LIMIT",
                     **kwargs: Any) -> dict: ...

    @abstractmethod
    def modify_order(self, order_id: str, order_type: str = "LIMIT", **kwargs: Any) -> dict: ...

    @abstractmethod
    def cancel_order(self, order_id: str, account_seq: int | None = None) -> dict: ...
