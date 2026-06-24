"""환경설정 로딩. 비밀키는 .env 에서만 읽고 코드/깃에 남기지 않는다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 미설치 시에도 환경변수만으로 동작
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


DEFAULT_BASE_URL = "https://openapi.tossinvest.com"


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str = DEFAULT_BASE_URL
    account_seq: int | None = None


def load_settings(dotenv_path: str | os.PathLike | None = None) -> Settings:
    """`.env` 또는 환경변수에서 설정을 읽는다.

    기본적으로 프로젝트 루트의 `.env` 를 자동 탐색한다.
    """
    if dotenv_path is None:
        # src/tossapi/config.py -> 프로젝트 루트는 3단계 위
        root = Path(__file__).resolve().parents[2]
        candidate = root / ".env"
        if candidate.exists():
            dotenv_path = candidate
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        load_dotenv()  # CWD 기준 .env 도 시도

    client_id = os.getenv("TOSS_CLIENT_ID", "").strip()
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError(
            "TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 가 설정되지 않았습니다. "
            ".env.example 을 복사해 .env 를 만들고 값을 채우세요."
        )

    base_url = os.getenv("TOSS_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL

    account_raw = os.getenv("TOSS_ACCOUNT_SEQ", "").strip()
    account_seq = int(account_raw) if account_raw else None

    return Settings(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url.rstrip("/"),
        account_seq=account_seq,
    )
