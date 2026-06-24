"""토스 API 예외 타입."""

from __future__ import annotations


class TossApiError(Exception):
    """API 에러 응답(4xx/5xx)을 표현한다."""

    def __init__(
        self,
        status_code: int,
        code: str | None = None,
        message: str | None = None,
        request_id: str | None = None,
        data: dict | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        self.data = data
        super().__init__(
            f"[{status_code}] code={code} message={message} requestId={request_id}"
        )


class TossAuthError(TossApiError):
    """OAuth2 토큰 발급/인증 실패."""


class RateLimitError(TossApiError):
    """요청 한도 초과(429)."""

    def __init__(self, *args, retry_after: float | None = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(*args, **kwargs)
