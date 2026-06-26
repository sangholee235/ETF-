"""봇 전략 설정. bot_config.json 으로 덮어쓸 수 있다."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "bot_config.json"


@dataclass
class BotConfig:
    # --- 대상 ---
    symbol: str = "069500"          # KODEX 200 (국내 지수형 ETF, 일반계좌도 매매차익 비과세)
    symbol_name: str = "KODEX 200"

    # --- 포트폴리오 (여러 ETF 동시 적립) ---
    portfolio_mode: bool = False    # True: 목표 비중 기반으로 매일 가장 부족한 ETF 적립
    portfolio: list = field(default_factory=list)  # [{symbol, name, weight}] weight 합=100 권장

    # --- 전략 (매수전용 적립) ---
    quantity_per_buy: int = 1        # 1회 매수 수량 (주)
    discount_pct: float = 0.005      # 전일 종가 대비 -0.5% 아래 지정가
    fallback_after_misses: int = 5   # N일 연속 미체결이면 시장가로 강제 매수 (상승장 누락 방지)
    tick_size: int = 5               # KRX ETF 호가단위 5원

    # --- 가드레일 (안전 한도) ---
    daily_budget_krw: int = 50_000   # 하루 최대 매수금액
    total_budget_krw: int = 0        # 누적 한도. 0 = 무제한
    require_market_open: bool = True  # 장 운영시간에만 주문

    # --- 스케줄러 (자동 적립) ---
    schedule_enabled: bool = False   # True: 매일 정해진 시각 자동 실행
    schedule_time: str = "09:05"     # HH:MM (KST). 평일 이 시각에 자동 적립 시도

    # --- 실행 모드 ---
    dry_run: bool = True             # True: 실주문 안 함(로그만). False: 실제 주문
    enabled: bool = True             # False: 봇 완전 정지 (킬스위치)

    @classmethod
    def load(cls) -> "BotConfig":
        cfg = cls()
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg

    def save(self) -> None:
        _CONFIG_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def round_to_tick(price: float, tick: int) -> int:
    """매수 지정가는 호가단위로 내림(보수적)."""
    return int(price // tick * tick)
