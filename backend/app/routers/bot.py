"""봇 상태/제어 라우터 (대시보드 적립탭용)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from tossapi import TossApiError

from brokers import available_brokers, default_broker

from ..bot.backtest import run_backtest, run_sweep
from ..bot.catalog import MAJOR_ETFS
from ..bot.config import BotConfig
from ..bot.runner import run_once
from ..bot.state import BotState
from ..deps import get_client, to_http

router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/scheduler")
def scheduler_status():
    """스케줄러 생존 상태 (자동화가 실제로 돌고 있는지 확인용)."""
    from ..bot.scheduler import heartbeat
    return heartbeat()


@router.get("/realtime")
def realtime_status():
    """실시간 체결(WebSocket) 연결 상태."""
    from ..bot import realtime
    return realtime.status()


@router.get("/market-status")
def market_status(broker: str | None = None):
    """지금 국내 정규장이 열려 있는지 (대시보드 배지용)."""
    from ..bot.guardrails import _is_market_open
    client = get_client(broker)
    try:
        return {"open": _is_market_open(client)}
    except Exception:
        return {"open": False}


@router.get("/stream")
async def stream():
    """실시간 체결통보 SSE 스트림 (프론트 EventSource 구독용)."""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from ..bot import realtime

    async def gen():
        q = realtime.hub.subscribe()
        try:
            yield "retry: 3000\n\n"            # 끊기면 3초 후 재연결
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"event: {ev.get('event', 'message')}\ndata: {json.dumps(ev.get('data'), ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"     # 프록시 타임아웃 방지 핑
        finally:
            realtime.hub.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/brokers")
def brokers():
    """동작 가능한 증권사 목록 + 기본값 (대시보드 계좌 분리용)."""
    return {"brokers": available_brokers(), "default": default_broker()}


@router.get("/status")
def status(broker: str | None = None):
    cfg = BotConfig.load(broker)
    state = BotState.load(broker)
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


_catalog_cache: dict[str, tuple[float, dict[str, str]]] = {}  # broker -> (ts, price_map)
_CATALOG_TTL = 15.0  # 초. 키움 레이트리밋(429) 완화용


@router.get("/preview")
def preview(broker: str | None = None):
    """실행하지 않고 '지금 적립하면 무슨 일이 일어날지' 미리보기 (상태 변경 없음).
    - 다음 적립 대상 ETF / 지정가 / 예상비용 / 가능·차단(사유)
    - 포트폴리오 목표비중 대비 현재 수렴 진행률
    - 시간과 무관한 구조적 경고(1주 비용 > 하루한도, 매수가능금액 < 예상비용)
    """
    from ..bot import guardrails
    from ..bot.portfolio import plan_daily_buys, waterfall_status

    cfg = BotConfig.load(broker)
    state = BotState.load(broker)
    client = get_client(broker)

    from ..bot.runner import _buying_power, _holdings_values, _portfolio_prices, _current

    # 현재 비중 = 실제 보유 평가금액 기준(못 읽으면 봇 누적투입 폴백)
    current_values = _holdings_values(client, cfg)
    invested = current_values if current_values is not None else (state.portfolio_invested or {})

    items = [p for p in cfg.portfolio if p.get("symbol")
             and (float(p.get("weight", 0)) > 0 or float(p.get("target", 0)) > 0)]
    total_inv = sum(float(invested.get(p["symbol"], 0)) for p in items)
    total_w = sum(float(p["weight"]) for p in items) or 1.0
    progress = [{
        "symbol": p["symbol"],
        "name": p.get("name", p["symbol"]),
        "targetWeight": float(p["weight"]) / total_w,
        "currentWeight": (float(invested.get(p["symbol"], 0)) / total_inv) if total_inv > 0 else 0.0,
        "investedKrw": int(float(invested.get(p["symbol"], 0))),
    } for p in items]

    fill_mode = getattr(cfg, "fill_mode", "weight")
    base = {"dryRun": cfg.dry_run, "enabled": cfg.enabled,
            "dailyBudgetKrw": cfg.daily_budget_krw, "progress": progress,
            "fillMode": fill_mode,
            "waterfall": waterfall_status(cfg, state) if fill_mode == "waterfall" else []}

    if not items:
        return {**base, "hasTarget": False,
                "reason": "적립할 ETF가 없습니다 — 아래에서 ETF와 목표비중을 추가하세요."}

    bp_cash = _buying_power(client)
    prices = _portfolio_prices(client, cfg)
    remaining_today = state.today_remaining_budget(cfg.daily_budget_krw)
    budget = min(remaining_today, bp_cash) if bp_cash is not None else remaining_today

    try:
        plan = plan_daily_buys(cfg, current_values or {}, prices, budget) if budget > 0 else []
    except Exception as e:
        return {**base, "hasTarget": True, "action": "SKIP", "blockReason": f"미리보기 실패: {e}"}

    if not plan:
        first = items[0]
        block = ("오늘 하루 한도를 이미 다 썼습니다 — 내일 다시 시도" if remaining_today <= 0
                 else "매수가능금액/오늘 남은 한도로 1주도 못 삽니다 — 입금이 필요합니다." if budget <= 0
                 else "오늘 살 게 없습니다 — 이미 목표 비중 도달.")
        return {**base, "hasTarget": True, "symbol": first["symbol"], "name": first.get("name", first["symbol"]),
                "action": "SKIP", "willTrade": False, "cashBuyingPower": bp_cash,
                "lastPrice": _current(client, first["symbol"]),
                "plan": [],
                "blockReason": block,
                "warnings": []}

    total_cost = sum(p["estCost"] for p in plan)
    guard = guardrails.check(client, cfg, state, total_cost, buying_power=bp_cash)

    name_by_symbol = {p["symbol"]: p.get("name", p["symbol"]) for p in items}
    plan_out = [{
        "symbol": it["symbol"], "name": name_by_symbol.get(it["symbol"], it["symbol"]),
        "quantity": it["quantity"], "price": it["price"], "estCost": it["estCost"],
    } for it in plan]

    warnings: list[str] = []
    if bp_cash is not None and bp_cash < total_cost:
        warnings.append(f"매수가능금액 {bp_cash:,}원이 예상비용 {total_cost:,}원보다 적습니다 — 입금이 필요합니다.")

    first = plan_out[0]
    return {
        **base,
        "hasTarget": True,
        "symbol": first["symbol"],
        "name": first["name"],
        "action": "MARKET_BUY",
        "quantity": first["quantity"],
        "price": None,                          # 그리디 매수는 전부 시장가
        "lastPrice": first["price"],
        "estCost": total_cost,
        "decisionReason": f"{len(plan_out)}개 종목 매수 예정 (목표비중 그리디 리밸런싱, 시장가)",
        "plan": plan_out,                       # 오늘 예정된 전체 매수 목록
        "willTrade": guard.ok,
        "blockReason": None if guard.ok else guard.reason,
        "cashBuyingPower": bp_cash,
        "warnings": warnings,
    }


@router.get("/catalog")
def catalog(broker: str | None = None):
    """주요 ETF 목록 + 현재가(클릭 선택용). 가격은 15초 캐시."""
    import time
    key = (broker or "").lower()
    now = time.time()
    cached = _catalog_cache.get(key)
    if cached and now - cached[0] < _CATALOG_TTL:
        price_map = cached[1]
    else:
        client = get_client(broker)
        symbols = ",".join(e["symbol"] for e in MAJOR_ETFS)
        price_map = {}
        try:
            for p in client.get_prices(symbols):
                price_map[p["symbol"]] = p.get("lastPrice")
        except Exception:  # 키움은 TossApiError 가 아닌 raw 예외를 던질 수 있음
            pass
        # 일부라도 받았으면 캐시 갱신 (전부 실패 시 직전 캐시 유지)
        if price_map or not cached:
            _catalog_cache[key] = (now, price_map)
        else:
            price_map = cached[1]
    return [{**e, "lastPrice": price_map.get(e["symbol"])} for e in MAJOR_ETFS]


class ConfigPatch(BaseModel):
    symbol: str | None = None
    symbol_name: str | None = None
    portfolio_mode: bool | None = None
    portfolio: list | None = None
    fill_mode: str | None = None
    wait_for_underweight: bool | None = None
    quantity_per_buy: int | None = None
    buy_amount_krw: int | None = None
    discount_pct: float | None = None
    fallback_after_misses: int | None = None
    daily_budget_krw: int | None = None
    total_budget_krw: int | None = None
    schedule_enabled: bool | None = None
    schedule_time: str | None = None
    dry_run: bool | None = None
    enabled: bool | None = None


@router.patch("/config")
def update_config(patch: ConfigPatch, broker: str | None = None):
    """대시보드에서 전략/한도 변경 (ETF 클릭 선택 포함)."""
    cfg = BotConfig.load(broker)
    for k, v in patch.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    cfg.save()
    return asdict(cfg)


@router.get("/backtest")
def backtest(symbol: str, days: int = 120, discount_pct: float = 0.005,
             fallback_after_misses: int = 5, quantity: int = 1,
             commission_pct: float = 0.0, broker: str | None = None):
    """적립봇 전략 vs 단순 매일 적립 백테스트."""
    try:
        return run_backtest(
            get_client(broker), symbol, days=days, discount_pct=discount_pct,
            fallback_after_misses=fallback_after_misses, quantity=quantity,
            commission_pct=commission_pct,
        )
    except TossApiError as e:
        raise to_http(e)


@router.get("/backtest/sweep")
def backtest_sweep(symbol: str, days: int = 120, quantity: int = 1,
                   commission_pct: float = 0.0, broker: str | None = None):
    """여러 (할인%, 전환일) 조합을 한 번에 백테스트해 최적값 탐색."""
    try:
        return run_sweep(get_client(broker), symbol, days=days, quantity=quantity,
                         commission_pct=commission_pct)
    except TossApiError as e:
        raise to_http(e)


@router.get("/logs")
def logs(limit: int = 200, broker: str | None = None):
    """전체 실행 로그 (최신순)."""
    state = BotState.load(broker)
    return list(reversed(state.logs))[:limit]


@router.post("/run")
def run(broker: str | None = None):
    """수동으로 적립 tick 1회 실행 (스케줄러 대신 버튼용).
    수동은 '하루 1회' 가드를 우회 — 미체결→취소 후 재시도가 가능하다."""
    return run_once(broker=broker, manual=True)


@router.post("/enabled")
def set_enabled(value: bool, broker: str | None = None):
    """킬스위치 on/off."""
    cfg = BotConfig.load(broker)
    cfg.enabled = value
    cfg.save()
    return {"enabled": cfg.enabled}
