"""포트폴리오(여러 ETF) 적립 — 목표 비중 대비 가장 부족한 종목을 고른다.

매 tick 마다 누적 투입(state.portfolio_invested) 기준 현재 비중을 계산하고,
목표 비중과의 차이가 가장 큰(가장 부족한) 종목을 선택해 적립한다.
→ 시간이 지나며 목표 비중에 수렴하는 '비중 추종 적립'.
"""

from __future__ import annotations

from .config import BotConfig
from .state import BotState


def select_underweight(cfg: BotConfig, state: BotState) -> tuple[str, str] | None:
    """(symbol, name) 반환. 포트폴리오가 비었으면 None."""
    items = [p for p in cfg.portfolio if p.get("symbol") and float(p.get("weight", 0)) > 0]
    if not items:
        return None

    total_weight = sum(float(p["weight"]) for p in items)
    invested = state.portfolio_invested or {}
    total_invested = sum(float(v) for v in invested.values())

    best = None
    best_deficit = -1e18
    for p in items:
        target = float(p["weight"]) / total_weight
        current = (float(invested.get(p["symbol"], 0)) / total_invested) if total_invested > 0 else 0.0
        deficit = target - current
        if deficit > best_deficit:
            best_deficit = deficit
            best = p
    if best is None:
        return None
    return best["symbol"], best.get("name", best["symbol"])
