"""봇 상태/제어 라우터 (대시보드 적립탭용)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from tossapi import TossApiError

from ..bot.backtest import run_backtest, run_sweep
from ..bot.catalog import MAJOR_ETFS
from ..bot.config import BotConfig
from ..bot.runner import run_once
from ..bot.state import BotState
from ..deps import get_client, to_http

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/status")
def status():
    cfg = BotConfig.load()
    state = BotState.load()
    return {
        "config": asdict(cfg),
        "state": {
            "totalInvestedKrw": state.total_invested_krw,
            "totalFilledQty": state.total_filled_qty,
            "consecutiveMisses": state.consecutive_misses,
            "lastTradeDate": state.last_trade_date,
            "logs": state.logs[-30:],
        },
    }


@router.get("/catalog")
def catalog():
    """주요 ETF 목록 + 현재가(클릭 선택용)."""
    client = get_client()
    symbols = ",".join(e["symbol"] for e in MAJOR_ETFS)
    price_map: dict[str, str] = {}
    try:
        for p in client.get_prices(symbols):
            price_map[p["symbol"]] = p.get("lastPrice")
    except TossApiError:
        pass
    return [{**e, "lastPrice": price_map.get(e["symbol"])} for e in MAJOR_ETFS]


class ConfigPatch(BaseModel):
    symbol: str | None = None
    symbol_name: str | None = None
    portfolio_mode: bool | None = None
    portfolio: list | None = None
    quantity_per_buy: int | None = None
    discount_pct: float | None = None
    fallback_after_misses: int | None = None
    daily_budget_krw: int | None = None
    total_budget_krw: int | None = None
    schedule_enabled: bool | None = None
    schedule_time: str | None = None
    dry_run: bool | None = None
    enabled: bool | None = None


@router.patch("/config")
def update_config(patch: ConfigPatch):
    """대시보드에서 전략/한도 변경 (ETF 클릭 선택 포함)."""
    cfg = BotConfig.load()
    for k, v in patch.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    cfg.save()
    return asdict(cfg)


@router.get("/backtest")
def backtest(symbol: str, days: int = 120, discount_pct: float = 0.005,
             fallback_after_misses: int = 5, quantity: int = 1,
             commission_pct: float = 0.0):
    """적립봇 전략 vs 단순 매일 적립 백테스트."""
    try:
        return run_backtest(
            get_client(), symbol, days=days, discount_pct=discount_pct,
            fallback_after_misses=fallback_after_misses, quantity=quantity,
            commission_pct=commission_pct,
        )
    except TossApiError as e:
        raise to_http(e)


@router.get("/backtest/sweep")
def backtest_sweep(symbol: str, days: int = 120, quantity: int = 1,
                   commission_pct: float = 0.0):
    """여러 (할인%, 전환일) 조합을 한 번에 백테스트해 최적값 탐색."""
    try:
        return run_sweep(get_client(), symbol, days=days, quantity=quantity,
                         commission_pct=commission_pct)
    except TossApiError as e:
        raise to_http(e)


@router.get("/logs")
def logs(limit: int = 200):
    """전체 실행 로그 (최신순)."""
    state = BotState.load()
    return list(reversed(state.logs))[:limit]


@router.post("/run")
def run():
    """수동으로 적립 tick 1회 실행 (스케줄러 대신 버튼용)."""
    return run_once()


@router.post("/enabled")
def set_enabled(value: bool):
    """킬스위치 on/off."""
    cfg = BotConfig.load()
    cfg.enabled = value
    cfg.save()
    return {"enabled": cfg.enabled}
