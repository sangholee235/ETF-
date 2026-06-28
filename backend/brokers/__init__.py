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


def default_broker() -> str:
    """기본 브로커 이름 (.env BROKER, 없으면 toss)."""
    _load_env()
    return os.getenv("BROKER", "toss").lower()


def get_broker(name: str | None = None) -> Broker:
    """브로커 인스턴스. name 미지정 시 .env BROKER 사용."""
    _load_env()
    name = (name or os.getenv("BROKER", "toss")).lower()
    if name == "kiwoom":
        from .kiwoom import KiwoomBroker
        return KiwoomBroker()
    from .toss import TossBroker
    return TossBroker()


def available_brokers() -> list[str]:
    """키가 설정된(=동작 가능한) 브로커 목록. 둘 다 있으면 [toss, kiwoom]."""
    _load_env()
    out: list[str] = []
    if os.getenv("TOSS_CLIENT_ID", "").strip() and os.getenv("TOSS_CLIENT_SECRET", "").strip():
        out.append("toss")
    if os.getenv("KIWOOM_APP_KEY", "").strip() and os.getenv("KIWOOM_SECRET_KEY", "").strip():
        out.append("kiwoom")
    return out or [default_broker()]


__all__ = ["Broker", "get_broker", "available_brokers", "default_broker"]
