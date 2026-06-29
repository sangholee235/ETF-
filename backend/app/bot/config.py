"""봇 전략 설정. bot_config.json 으로 덮어쓸 수 있다."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 상태/설정 보관 디렉터리. 컨테이너에선 TOSSAPI_DATA_DIR(볼륨)로 분리.
_DATA_DIR = Path(os.getenv("TOSSAPI_DATA_DIR") or Path(__file__).resolve().parents[2])
_LEGACY_CONFIG_PATH = _DATA_DIR / "bot_config.json"


def _resolve_broker(broker: str | None) -> str:
    return (broker or os.getenv("BROKER", "toss")).lower()


def _config_path(broker: str | None) -> Path:
    """브로커별 설정 파일 경로 (bot_config_{broker}.json)."""
    return _DATA_DIR / f"bot_config_{_resolve_broker(broker)}.json"


@dataclass
class BotConfig:
    # --- 대상 ---
    symbol: str = "069500"          # KODEX 200 (국내 지수형 ETF, 일반계좌도 매매차익 비과세)
    symbol_name: str = "KODEX 200"

    # --- 포트폴리오 (여러 ETF 동시 적립) ---
    portfolio_mode: bool = False    # True: 목표 비중 기반으로 매일 가장 부족한 ETF 적립
    portfolio: list = field(default_factory=list)  # [{symbol, name, weight, target}]
    # fill_mode: weight=목표비중 추종 / waterfall=우선순위 순서대로 목표금액(target)까지 채우고 다음
    fill_mode: str = "weight"
    # 비중추종에서 가장 부족한(보통 비싼) ETF를 못 살 때:
    #   False = 살 수 있는 다른 목표미달 ETF라도 산다 (기본, 돈 안 놀림)
    #   True  = 그것만 사려고 기다린다 (현금 모음, 비중 정확 유지)
    wait_for_underweight: bool = False

    # --- 전략 (매수전용 적립) ---
    quantity_per_buy: int = 1        # 1회 매수 수량 (주). buy_amount_krw=0 일 때 사용
    buy_amount_krw: int = 0          # 1회 적립 금액(원). >0 이면 이 금액 안에서 살 수 있는 만큼 매수
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
    def load(cls, broker: str | None = None) -> "BotConfig":
        cfg = cls()
        cfg._broker = _resolve_broker(broker)
        path = _config_path(broker)
        # 브로커별 파일이 없으면 레거시(bot_config.json)에서 1회 마이그레이션 읽기
        src = path if path.exists() else _LEGACY_CONFIG_PATH
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        return cfg

    def save(self) -> None:
        _config_path(getattr(self, "_broker", None)).write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def round_to_tick(price: float, tick: int) -> int:
    """매수 지정가는 호가단위로 내림(보수적)."""
    return int(price // tick * tick)
