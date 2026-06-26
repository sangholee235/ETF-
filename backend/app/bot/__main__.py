"""봇 CLI.

    python -m app.bot run       # 적립 tick 1회 실행
    python -m app.bot status    # 현재 상태/설정 출력
    python -m app.bot stop      # 킬스위치 (enabled=False)
    python -m app.bot start     # 재가동 (enabled=True)

backend/ 디렉터리에서 실행. 기본은 DRY_RUN(실주문 없음).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.bot.config import BotConfig  # noqa: E402
from app.bot.state import BotState  # noqa: E402
from app.bot.runner import run_once  # noqa: E402


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "run":
        print(json.dumps(run_once(), ensure_ascii=False, indent=2))
    elif cmd == "status":
        cfg = BotConfig.load()
        state = BotState.load()
        print("=== 설정 ===")
        print(f"  대상: {cfg.symbol_name}({cfg.symbol})  모드: {'DRY_RUN' if cfg.dry_run else 'LIVE'}  활성: {cfg.enabled}")
        print(f"  1회 {cfg.quantity_per_buy}주, 전일종가 -{cfg.discount_pct*100:.1f}% 지정가, {cfg.fallback_after_misses}일 미체결시 시장가")
        print(f"  한도: 하루 {cfg.daily_budget_krw:,}원 / 누적 {cfg.total_budget_krw:,}원")
        print("=== 상태 ===")
        print(f"  누적투입: {state.total_invested_krw:,}원  보유(추정): {state.total_filled_qty}주  연속미체결: {state.consecutive_misses}")
        print(f"  최근 로그 {min(5, len(state.logs))}건:")
        for lg in state.logs[-5:]:
            print(f"    {lg['ts'][:19]} [{lg['mode']}] {lg['action']} {lg.get('price','')} - {lg['reason']}")
    elif cmd in ("stop", "start"):
        cfg = BotConfig.load()
        cfg.enabled = cmd == "start"
        cfg.save()
        print(f"봇 {'가동' if cfg.enabled else '정지(킬스위치)'} 됨.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
