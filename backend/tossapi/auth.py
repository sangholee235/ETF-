"""OAuth2 Client Credentials 토큰 관리.

- client 당 유효 토큰은 1개이며 재발급 시 이전 토큰은 무효화된다.
- refresh token 이 없으므로 만료 시 동일 엔드포인트로 재발급한다.
- 토큰은 메모리에 캐시하고, 만료 약간 전에 선제 재발급한다.
"""

from __future__ import annotations

import threading
import time

import requests

from .errors import TossAuthError

# 만료 이 시간(초) 전이면 미리 재발급
_EXPIRY_MARGIN = 60


class TokenManager:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = f"{base_url.rstrip('/')}/oauth2/token"
        self._session = session or requests.Session()
        self._timeout = timeout

        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            now = time.monotonic()
            if (
                not force_refresh
                and self._access_token
                and now < self._expires_at - _EXPIRY_MARGIN
            ):
                return self._access_token
            return self._issue()

    def invalidate(self) -> None:
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0

    def _issue(self) -> str:
        try:
            resp = self._session.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise TossAuthError(0, code="network-error", message=str(exc)) from exc

        if resp.status_code != 200:
            err = _safe_json(resp)
            raise TossAuthError(
                resp.status_code,
                code=err.get("error", "auth-failed"),
                message=err.get("error_description", resp.text[:200]),
            )

        body = resp.json()
        self._access_token = body["access_token"]
        self._expires_at = time.monotonic() + float(body.get("expires_in", 0))
        return self._access_token


def _safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {}
