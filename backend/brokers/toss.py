"""토스증권 브로커 구현. 기존 TossClient 가 모든 메서드를 이미 갖고 있어 그대로 사용한다."""

from __future__ import annotations

from tossapi import TossClient

from .base import Broker


class TossBroker(TossClient, Broker):
    """TossClient 의 구현이 Broker 인터페이스를 그대로 충족한다."""
    pass
