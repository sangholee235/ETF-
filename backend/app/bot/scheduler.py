"""자동 적립 스케줄러.

외부 의존성 없이 데몬 스레드로 매분 현재(KST) 시각을 확인하고,
장 개장 직후 고정 시각(MARKET_OPEN_TRIGGER)에 run_once 를 호출한다.
그리디 매수는 예산 소진까지 알아서 반복돼 시작 시각이 결과에 큰 영향이
없어서, 사용자가 고를 값(cfg.schedule_time)이 아니라 상수로 고정한다
(동시호가 직후 몇 분은 시세가 불안정할 수 있어 개장+5분).
하루 1회 가드레일(already_traded_today)이 중복 매수를 막는다.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from .config import BotConfig
from .runner import run_once

_KST = timezone(timedelta(hours=9))
MARKET_OPEN_TRIGGER = "09:05"  # 장 개장(09:00) + 5분(동시호가 안정화). cfg.schedule_time 은 더 이상 사용 안 함.
_thread: threading.Thread | None = None
_stop = threading.Event()
_last_fired: dict[str, str] = {}  # broker -> "broker YYYY-MM-DD HH:MM"
_last_tick: datetime | None = None       # 스케줄러가 마지막으로 점검한 시각 (심장박동)
_started_at: datetime | None = None
_last_fired_at: dict[str, str] = {}       # broker -> 마지막 실제 실행 시각(ISO)


def _loop() -> None:
    global _last_tick
    while not _stop.is_set():
        try:
            from brokers import available_brokers
            now = datetime.now(_KST)
            _last_tick = now                 # 매 점검마다 갱신 → "살아있음" 증거
            hhmm = now.strftime("%H:%M")
            weekday = now.weekday() < 5  # 월~금
            for broker in available_brokers():
                cfg = BotConfig.load(broker)
                if not (cfg.schedule_enabled and cfg.enabled):
                    continue
                key = f"{broker} {_stamp(now)}"  # 브로커별로 분당 1회만
                if weekday and hhmm == MARKET_OPEN_TRIGGER and _last_fired.get(broker) != key:
                    _last_fired[broker] = key
                    _last_fired_at[broker] = now.isoformat()
                    run_once(broker=broker)
        except Exception:  # 스케줄러는 죽지 않게 모든 예외 흡수
            pass
        _stop.wait(30)  # 30초마다 점검


def heartbeat() -> dict:
    """스케줄러 생존 상태. lastTick 이 최근(~35초 내)이면 정상 동작 중."""
    now = datetime.now(_KST)
    alive = bool(_thread and _thread.is_alive())
    fresh = _last_tick is not None and (now - _last_tick).total_seconds() < 40
    return {
        "alive": alive and fresh,
        "threadAlive": alive,
        "lastTick": _last_tick.isoformat() if _last_tick else None,
        "secondsSinceTick": int((now - _last_tick).total_seconds()) if _last_tick else None,
        "startedAt": _started_at.isoformat() if _started_at else None,
        "lastFiredAt": dict(_last_fired_at),
        "now": now.isoformat(),
    }


def _stamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M")


def start() -> None:
    global _thread, _started_at
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _started_at = datetime.now(_KST)
    _thread = threading.Thread(target=_loop, name="bot-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
