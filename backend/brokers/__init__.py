"""증권사 브로커 추상화.

봇·전략·라우터는 `Broker` 인터페이스에만 의존하므로,
환경변수 BROKER=toss|kiwoom 으로 증권사를 갈아끼울 수 있다.
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import Broker


def _load_env() -> None:
    """BROKER 등 env 를 .env 에서 먼저 로드 (브로커 선택 전에 필요)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    here = Path(__file__).resolve()
    for env_path in (here.parents[1] / ".env", here.parents[2] / ".env"):
        if env_path.exists():
            load_dotenv(env_path)


def get_broker() -> Broker:
    _load_env()
    name = os.getenv("BROKER", "toss").lower()
    if name == "kiwoom":
        from .kiwoom import KiwoomBroker
        return KiwoomBroker()
    from .toss import TossBroker
    return TossBroker()


__all__ = ["Broker", "get_broker"]
