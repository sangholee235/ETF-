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
    under_target = [p for p in items if deficit_of(p) > 1e-9]

    # 완전 균형(부족한 ETF가 하나도 없음)이면: 현금을 놀리지 않는다.
    # 목표 비중 그대로 유지하며 계속 적립하도록 전체를 후보로 본다.
    # (하나 사면 살짝 초과 → 다음엔 나머지가 부족 → 돌아가며 균형 유지하며 투입)
    pool = under_target if under_target else items

    # "기다림" 모드: 전체에서 가장 부족한 ETF를 못 사면 차순위를 사지 않고 기다린다.
    # (균형 상태면 '기다릴 미달 종목'이 없으므로 그냥 적립한다)
    if getattr(cfg, "wait_for_underweight", False) and affordable is not None and under_target:
        top = max(pool, key=deficit_of)
        if top["symbol"] not in affordable:
            return None  # 비싼 1순위 살 돈 모일 때까지 대기

    candidates = pool if affordable is None else [p for p in pool if p["symbol"] in affordable]
    if not candidates:
        return None
    best = max(candidates, key=deficit_of)
    return best["symbol"], best.get("name", best["symbol"])


# 시장가 매수는 체결가가 어디로 튈지 몰라, 증권사가 상한가(현재가 +30%, KRX 가격제한폭)
# 기준으로 증거금을 미리 잡아둔다. 그래서 현재가만 보고 수량을 정하면 실제로는
# '매수증거금 부족'으로 거부될 수 있다(실사례로 확인됨) — 수량은 이 버퍼로 보수적으로
# 계산하고, 실제 표시/비용은 진짜 현재가로 그대로 보여준다(사용자에게 부풀려 안 보임).
_MARKET_ORDER_MARGIN_BUFFER = 1.3


def plan_daily_buys(cfg: BotConfig, current_values: dict, prices: dict,
                    budget: int, max_iters: int = 30) -> list[dict]:
    """하루 예산을 목표 비중대로 그리디하게 여러 종목에 나눠 쓰는 매수 계획을 세운다.

    매 반복마다 '지금 가장 부족한 종목'을 다시 계산해 그 종목이 정확히 목표 비중이
    되는 데 필요한 금액만큼만 산다(오버슈팅 방지). 필요금액이 1주 값도 안 되면
    다음으로 부족한 종목을 시도하고, 아무도 부족하지 않으면(균형) 가장 덜 과대비중인
    종목을 1주씩 사서 예산을 남기지 않는다. 예산이 다하거나 1주도 못 살 때까지 반복.

    수량은 시장가 증거금 버퍼(_MARKET_ORDER_MARGIN_BUFFER)를 적용해 보수적으로 계산해
    '매수증거금 부족' 거부를 피한다.

    current_values: {symbol: 현재 평가금액}. prices: {symbol: 현재가}.
    반환: [{"symbol","quantity","price","estCost"}, ...] 실행 순서대로.
    """
    items = [p for p in cfg.portfolio
            if p.get("symbol") and float(p.get("weight", 0)) > 0 and p["symbol"] in prices]
    if not items:
        return []

    total_weight = sum(float(p["weight"]) for p in items)
    values = {p["symbol"]: float(current_values.get(p["symbol"], 0)) for p in items}
    plan: list[dict] = []
    remaining = budget

    def ideal_needed(p: dict, total_v: float) -> float:
        """이 종목이 정확히 목표비중이 되는 데 필요한 추가 매수 금액(음수=이미 초과).
        총자산 0(콜드스타트)이면 공식이 자연히 0을 내어 '균형' 분기로 빠지고,
        거기서 비중 큰 것부터 1주씩 사며 자연스럽게 시작한다(몰빵 방지)."""
        w = float(p["weight"]) / total_weight
        if w >= 1:
            return float(remaining)
        return (w * total_v - values[p["symbol"]]) / (1 - w)

    for _ in range(max_iters):
        if remaining <= 0:
            break
        total_v = sum(values.values())
        # 필요금액 내림차순, 동점(콜드스타트 등)이면 목표비중 큰 것부터
        ranked = sorted(items, key=lambda p: (ideal_needed(p, total_v), float(p["weight"])), reverse=True)

        chosen_sym = None
        qty = 0
        price = 0
        for p in ranked:
            need = ideal_needed(p, total_v)
            if need <= 0:
                continue  # 진짜 부족(양수)인 것만 여기서 시도
            sym = p["symbol"]
            price = prices[sym]
            qty = int(min(need, remaining) // (price * _MARKET_ORDER_MARGIN_BUFFER))
            if qty >= 1:
                chosen_sym = sym
                break

        if chosen_sym is None:
            # 부족한 종목이 없거나 다 1주도 안 됨 → 균형 유지: 가장 덜 과대비중인 종목 1주만
            for p in ranked:
                sym = p["symbol"]
                price = prices[sym]
                if price * _MARKET_ORDER_MARGIN_BUFFER <= remaining:
                    chosen_sym, qty = sym, 1
                    break
            if chosen_sym is None:
                break  # 뭘 사도 예산 초과 → 오늘은 여기까지

        cost = qty * price
        if cost > remaining:
            break
        plan.append({"symbol": chosen_sym, "quantity": qty, "price": price, "estCost": cost})
        values[chosen_sym] = values.get(chosen_sym, 0) + cost
        remaining -= cost

    return plan


def has_underweight_target(cfg: BotConfig, current_values: dict, prices: dict) -> bool:
    """진짜로 목표비중보다 부족한(양수 ideal_needed) 종목이 하나라도 있는지 —
    '예산이 부족해서 1주도 못 사는' 상태와 진짜 '균형(목표비중 도달)' 상태를 구분하는 데 쓴다.

    주의: plan_daily_buys(budget=매우 큰 값)로 흉내내면 안 된다 — 그 함수엔 '완전
    균형이어도 현금 안 놀리려고 1주씩 계속 산다'는 폴백이 있어서, 예산을 무한으로
    주면 균형 여부와 무관하게 항상 뭔가를 사버려(True만 나옴, 실측로 확인됨).
    그래서 여기선 그 폴백 없이 ideal_needed 부호만 순수하게 확인한다."""
    items = [p for p in cfg.portfolio
            if p.get("symbol") and float(p.get("weight", 0)) > 0 and p["symbol"] in prices]
    if not items:
        return False

    total_weight = sum(float(p["weight"]) for p in items)
    total_v = sum(float(current_values.get(p["symbol"], 0)) for p in items)

    # 콜드스타트(투자 0원): ideal_needed 공식은 자연히 0을 내어(진짜 부족과 구분 안 됨)
    # plan_daily_buys 에선 '균형 분기'로 자연스럽게 시작하지만, 여기선 그걸 "이미 목표
    # 비중 도달"로 오인하면 안 되므로 명시적으로 '부족함'으로 취급한다.
    if total_v <= 0:
        return True

    for p in items:
        w = float(p["weight"]) / total_weight
        value = float(current_values.get(p["symbol"], 0))
        need = float("inf") if w >= 1 else (w * total_v - value) / (1 - w)
        if need > 0:
            return True
    return False
