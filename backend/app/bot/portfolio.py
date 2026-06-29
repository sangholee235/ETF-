"""포트폴리오(여러 ETF) 적립 — 목표 비중 대비 가장 부족한 종목을 고른다.

매 tick 마다 누적 투입(state.portfolio_invested) 기준 현재 비중을 계산하고,
목표 비중과의 차이가 가장 큰(가장 부족한) 종목을 선택해 적립한다.
→ 시간이 지나며 목표 비중에 수렴하는 '비중 추종 적립'.
"""

from __future__ import annotations

from .config import BotConfig
from .state import BotState


def select_target(cfg: BotConfig, state: BotState,
                  affordable: set[str] | None = None,
                  current_values: dict | None = None) -> tuple[str, str] | None:
    """fill_mode 에 따라 적립 대상 ETF 선택. weight=비중추종, waterfall=우선순위.

    current_values: {symbol: 현재 평가금액}. 주면 '실제 보유 비중' 기준으로 판단한다
    (봇이 산 것만이 아니라 기존 보유분 포함). 없으면 봇 누적투입 기준.
    """
    if getattr(cfg, "fill_mode", "weight") == "waterfall":
        return select_waterfall(cfg, state, affordable)
    return select_underweight(cfg, state, affordable, current_values)


def select_waterfall(cfg: BotConfig, state: BotState,
                     affordable: set[str] | None = None) -> tuple[str, str] | None:
    """우선순위(리스트 순서)대로 목표금액(target)까지 채우고 다음으로 내려간다.
    살 수 있는(affordable) 것 중, 아직 목표금액 미달인 가장 위 ETF를 고른다."""
    invested = state.portfolio_invested or {}
    for p in cfg.portfolio:
        sym = p.get("symbol")
        if not sym:
            continue
        target = float(p.get("target", 0) or 0)
        if target <= 0:
            continue
        if float(invested.get(sym, 0)) >= target:
            continue  # 이미 완료(채워짐)
        if affordable is not None and sym not in affordable:
            continue  # 못 사는 건 건너뜀 (다음 우선순위 시도)
        return sym, p.get("name", sym)
    return None


def waterfall_status(cfg: BotConfig, state: BotState) -> list[dict]:
    """각 ETF의 워터폴 상태: done(완료)/active(진행중)/wait(대기) + 투입/목표."""
    invested = state.portfolio_invested or {}
    out: list[dict] = []
    active_found = False
    for p in cfg.portfolio:
        sym = p.get("symbol")
        if not sym:
            continue
        target = float(p.get("target", 0) or 0)
        inv = float(invested.get(sym, 0))
        if target > 0 and inv >= target:
            status = "done"
        elif not active_found and target > 0:
            status = "active"; active_found = True
        else:
            status = "wait"
        out.append({
            "symbol": sym, "name": p.get("name", sym),
            "investedKrw": int(inv), "targetKrw": int(target),
            "fillPct": min(1.0, inv / target) if target > 0 else 0.0,
            "status": status,
        })
    return out


def select_underweight(cfg: BotConfig, state: BotState,
                       affordable: set[str] | None = None,
                       current_values: dict | None = None) -> tuple[str, str] | None:
    """목표 비중 대비 가장 부족한 ETF (symbol, name) 반환.

    affordable 가 주어지면 그 안의 종목만 후보로 본다(=살 수 있는 것만).
    current_values(실제 보유 평가금액)가 있으면 그 기준, 없으면 봇 누적투입 기준으로 현재 비중 계산.

    wait_for_underweight=True 면: 전체에서 가장 부족한 ETF가 못 사는 거면 None(기다림).
    살 수 있는 후보가 없으면 None.
    """
    items = [p for p in cfg.portfolio if p.get("symbol") and float(p.get("weight", 0)) > 0]
    if not items:
        return None

    total_weight = sum(float(p["weight"]) for p in items)
    invested = current_values if current_values is not None else (state.portfolio_invested or {})
    total_invested = sum(float(invested.get(p["symbol"], 0)) for p in items)

    def deficit_of(p) -> float:
        target = float(p["weight"]) / total_weight
        current = (float(invested.get(p["symbol"], 0)) / total_invested) if total_invested > 0 else 0.0
        return target - current

    # 목표 미달(deficit>0) ETF만 후보. 이미 목표 넘으면 더 안 산다(과매수 방지).
    under_target = [p for p in items if deficit_of(p) > 0]
    if not under_target:
        return None

    # "기다림" 모드: 전체에서 가장 부족한 ETF를 못 사면 차순위를 사지 않고 기다린다.
    if getattr(cfg, "wait_for_underweight", False) and affordable is not None:
        top = max(under_target, key=deficit_of)
        if top["symbol"] not in affordable:
            return None  # 비싼 1순위 살 돈 모일 때까지 대기

    candidates = under_target if affordable is None else [p for p in under_target if p["symbol"] in affordable]
    if not candidates:
        return None
    best = max(candidates, key=deficit_of)
    return best["symbol"], best.get("name", best["symbol"])
