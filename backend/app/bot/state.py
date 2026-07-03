"""봇의 영속 상태 + 주문 로그. JSON 파일에 저장 (data/bot_state.json)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

_DATA_DIR = Path(os.getenv("TOSSAPI_DATA_DIR") or Path(__file__).resolve().parents[2])
_LEGACY_STATE_PATH = _DATA_DIR / "data" / "bot_state.json"


def _resolve_broker(broker: str | None) -> str:
    return (broker or os.getenv("BROKER", "toss")).lower()


def _state_path(broker: str | None) -> Path:
    return _DATA_DIR / "data" / f"bot_state_{_resolve_broker(broker)}.json"


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
    today_budget_used_krw: int = 0    # 오늘 하루 한도 중 이미 쓴 금액 (날짜 바뀌면 리셋)
    today_budget_date: str | None = None

    @classmethod
    def load(cls, broker: str | None = None) -> "BotState":
        st = cls()
        st._broker = _resolve_broker(broker)
        path = _state_path(broker)
        src = path if path.exists() else _LEGACY_STATE_PATH
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(st, k):
                    setattr(st, k, v)
        return st

    def save(self) -> None:
        path = _state_path(getattr(self, "_broker", None))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_log(self, log: OrderLog) -> None:
        self.logs.append(asdict(log))
        self.logs = self.logs[-500:]  # 최근 500건만 유지

    def already_traded_today(self) -> bool:
        return self.last_trade_date == date.today().isoformat()

    def today_remaining_budget(self, daily_budget_krw: int) -> int:
        """오늘 하루 한도 중 아직 안 쓴 금액. 날짜 바뀌면 자동으로 리셋된 것처럼 전액 반환
        (실제 리셋은 record_today_spend 가 다음 지출 시점에 해준다)."""
        if self.today_budget_date != date.today().isoformat():
            return max(0, daily_budget_krw)
        return max(0, daily_budget_krw - self.today_budget_used_krw)

    def record_today_spend(self, amount: int) -> None:
        """장중 여러 번 실행돼도 오늘 쓴 금액을 누적 추적 (날짜 바뀌면 리셋)."""
        today = date.today().isoformat()
        if self.today_budget_date != today:
            self.today_budget_date = today
            self.today_budget_used_krw = 0
        self.today_budget_used_krw += amount
