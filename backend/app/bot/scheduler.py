"""자동 적립 스케줄러.

외부 의존성 없이 데몬 스레드로 매분 현재(KST) 시각을 확인하고,
장중(개장+5분 ~ 마감-10분) CHECK_INTERVAL_MIN 간격으로 run_once 를 반복 호출한다.

'하루 1회'가 아니라 '하루 한도를 오늘 얼마나 썼는지'로 관리되므로(runner.py,
state.today_remaining_budget), 아침에 예산이 남았거나(1주도 못 사서 SKIP),
장중에 입금이 들어오거나, 가격이 떨어져 이제 살 수 있게 되면 다음 주기적
체크에서 자동으로 이어서 산다 — "장중 계속 감시하며 하나라도 더 사려는" 동작.

그리디 매수 자체는 한 번 실행될 때 예산을 다 쓸 때까지 내부에서 반복하므로,
이 주기적 체크는 그 사이(장중 새 기회)를 잡기 위한 것이지 매번 크게 사는 게
아니다 — 대부분의 실행은 "오늘 살 게 없음"으로 조용히 끝난다.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from .config import BotConfig
from .runner import run_once

_KST = timezone(timedelta(hours=9))
_CHECK_START = (9, 5)     # 개장(09:00) + 5분(동시호가 안정화)
_CHECK_END = (15, 20)     # 마감(15:30) 10분 전까지만 (막판 변동성 회피)
CHECK_INTERVAL_MIN = 10   # 장중 재확인 간격(분)
_thread: threading.Thread | None = None
_stop = threading.Event()
_last_fired: dict[str, str] = {}  # broker -> "broker YYYY-MM-DD HH:MM"
_last_tick: datetime | None = None       # 스케줄러가 마지막으로 점검한 시각 (심장박동)
_started_at: datetime | None = None
_last_fired_at: dict[str, str] = {}       # broker -> 마지막 실제 실행 시각(ISO)


def _should_check(now: datetime) -> bool:
    """장중이고, 개장 기준 CHECK_INTERVAL_MIN 배수 시점인지."""
    if now.weekday() >= 5:  # 토/일
        return False
    start_min = _CHECK_START[0] * 60 + _CHECK_START[1]
    end_min = _CHECK_END[0] * 60 + _CHECK_END[1]
    now_min = now.hour * 60 + now.minute
    if not (start_min <= now_min <= end_min):
        return False
    return (now_min - start_min) % CHECK_INTERVAL_MIN == 0


def _loop() -> None:
    global _last_tick
    while not _stop.is_set():
        try:
            from brokers import available_brokers
            now = datetime.now(_KST)
            _last_tick = now                 # 매 점검마다 갱신 → "살아있음" 증거
            if _should_check(now):
                for broker in available_brokers():
                    cfg = BotConfig.load(broker)
                    if not (cfg.schedule_enabled and cfg.enabled):
                        continue
                    key = f"{broker} {_stamp(now)}"  # 브로커별로 분당 1회만
                    if _last_fired.get(broker) != key:
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
