"""자동 적립 스케줄러.

외부 의존성 없이 데몬 스레드로 매분 현재(KST) 시각을 확인하고,
config.schedule_time 과 일치하면 run_once 를 호출한다.
하루 1회 가드레일(already_traded_today)이 중복 매수를 막는다.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from .config import BotConfig
from .runner import run_once

_KST = timezone(timedelta(hours=9))
_thread: threading.Thread | None = None
_stop = threading.Event()
_last_fired_minute: str | None = None


def _loop() -> None:
    global _last_fired_minute
    while not _stop.is_set():
        try:
            cfg = BotConfig.load()
            if cfg.schedule_enabled and cfg.enabled:
                now = datetime.now(_KST)
                hhmm = now.strftime("%H:%M")
                weekday = now.weekday() < 5  # 월~금
                if weekday and hhmm == cfg.schedule_time and _last_fired_minute != _stamp(now):
                    _last_fired_minute = _stamp(now)
                    run_once()
        except Exception:  # 스케줄러는 죽지 않게 모든 예외 흡수
            pass
        _stop.wait(30)  # 30초마다 점검


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M")


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="bot-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
