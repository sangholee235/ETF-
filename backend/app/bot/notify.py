"""알림(디스코드 웹훅). 설정 없으면 조용히 무시. 실패가 봇을 막지 않는다."""

from __future__ import annotations

import json
import os
import urllib.request


def discord(message: str) -> None:
    """DISCORD_WEBHOOK_URL 로 메시지 전송(동기). 미설정/실패 시 조용히 넘어감."""
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        data = json.dumps({"content": message}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # 알림 실패가 매매/봇을 막으면 안 됨
