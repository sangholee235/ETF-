"""공유 의존성: TossClient 싱글턴과 에러 변환."""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException

from tossapi import TossApiError

from brokers import Broker, get_broker


@lru_cache(maxsize=1)
def get_client() -> Broker:
    """현재 설정된 증권사 브로커 (BROKER=toss|kiwoom)."""
    return get_broker()


def to_http(exc: TossApiError) -> HTTPException:
    """TossApiError -> FastAPI HTTPException 변환."""
    status = exc.status_code if 400 <= exc.status_code < 600 else 502
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message, "requestId": exc.request_id},
    )
