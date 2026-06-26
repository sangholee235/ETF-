"""키움 REST 인증 테스트.

실행 (backend 디렉터리에서):
    # .env 에 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 입력 후
    python scripts/kiwoom_test.py

토큰 발급(au10001)이 되는지부터 확인한다. 시세/주문은 각 TR 명세를 받아 추가.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

from brokers.kiwoom import KiwoomBroker  # noqa: E402


def main() -> None:
    kw = KiwoomBroker()
    print(f"서버: {kw.base_url}")
    if not kw.app_key or not kw.secret_key:
        print("⚠️  KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 를 .env 에 넣어주세요.")
        return
    print("토큰 발급 시도...")
    token = kw._get_token()
    masked = token[:8] + "..." + token[-6:] if len(token) > 16 else "(short)"
    print(f"✅ 토큰 발급 성공: {masked}")
    print(f"   만료: {kw._token_exp}")


if __name__ == "__main__":
    main()
