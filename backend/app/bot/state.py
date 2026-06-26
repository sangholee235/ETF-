"""봇의 영속 상태 + 주문 로그. JSON 파일에 저장 (data/bot_state.json)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "bot_state.json"


@dataclass
class OrderLog:
    ts: str                 # ISO 시각
    trade_date: str         # YYYY-MM-DD
    mode: str               # DRY_RUN | LIVE
    action: str             # LIMIT_BUY | MARKET_BUY | SKIP
    reason: str
    symbol: str
    quantity: int = 0
    price: int | None = None
    order_id: str | None = None
    client_order_id: str | None = None
    filled: bool | None = None   # 다음 tick 에서 체결 확인 후 갱신


@dataclass
class BotState:
    consecutive_misses: int = 0
    total_invested_krw: int = 0       # 체결 기준 누적 투입(추정)
    total_filled_qty: int = 0
    last_trade_date: str | None = None
    last_open_order_id: str | None = None  # 직전 미체결 주문 (다음 tick 에 체결확인)
    last_client_order_id: str | None = None
    portfolio_invested: dict = field(default_factory=dict)  # {symbol: 누적 투입 KRW}
    logs: list = field(default_factory=list)  # list[dict]

    @classmethod
    def load(cls) -> "BotState":
        if _STATE_PATH.exists():
            data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            st = cls()
            for k, v in data.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            return st
        return cls()

    def save(self) -> None:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_log(self, log: OrderLog) -> None:
        self.logs.append(asdict(log))
        self.logs = self.logs[-500:]  # 최근 500건만 유지

    def already_traded_today(self) -> bool:
        return self.last_trade_date == date.today().isoformat()
