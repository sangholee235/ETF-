"""공유 의존성: 브로커 싱글턴(브로커별 캐시)과 에러 변환."""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, Query

from tossapi import TossApiError

from brokers import Broker, get_broker


@lru_cache(maxsize=8)
def get_client(broker: str | None = None) -> Broker:
    """브로커 인스턴스 (브로커별 1개 캐시). broker=None 이면 .env BROKER."""
    return get_broker(broker)


def client_dep(broker: str | None = Query(None, description="toss | kiwoom")) -> Broker:
    """라우터용 FastAPI 의존성. ?broker= 쿼리로 증권사 선택."""
    return get_client(broker)


def to_http(exc: TossApiError) -> HTTPException:
    """TossApiError -> FastAPI HTTPException 변환."""
    status = exc.status_code if 400 <= exc.status_code < 600 else 502
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message, "requestId": exc.request_id},
    )


def to_http_any(exc: Exception) -> HTTPException:
    """TossApiError/RuntimeError(키움 등 다른 브로커의 실패) 공통 변환.
    키움은 토큰·TR 실패를 TossApiError 가 아니라 RuntimeError 로 던지는데,
    라우터가 TossApiError 만 잡으면 처리 안 된 500이 그대로 새고 프론트의
    .catch(() => {})가 조용히 삼켜서 '에러도 없이 그냥 - 만 뜨는' 증상이 생긴다."""
    if isinstance(exc, TossApiError):
        return to_http(exc)
    return HTTPException(status_code=502, detail=str(exc))
