"""키움 실시간 주문체결(WebSocket) → SSE 브로드캐스트.

키움 wss 로 LOGIN → REG(주문체결 type '00') 등록 후, REAL 수신 시
필요한 필드만 추려 구독 중인 프론트(EventSource)로 밀어준다.

설계상 '체결통보'만 한다(시세/호가 실시간 X). 봇 상태(누적/연속미체결)는
기존 폴링 confirm 경로가 담당하고, 여기선 화면 즉시 갱신용 알림만 보낸다.
"""

from __future__ import annotations

import asyncio
import json
import contextlib
from typing import Any

# 주문체결(type '00') 실시간 FID 맵 (키움 명세)
_FID = {
    "9203": "orderId",        # 주문번호
    "905": "side",            # 주문구분 (+매수/-매도)
    "906": "orderType",       # 매매구분 (지정가/시장가)
    "9001": "symbol",         # 종목코드
    "302": "name",            # 종목명
    "913": "orderStatus",     # 주문상태 (접수/체결/확인/거부)
    "900": "orderQty",        # 주문수량
    "901": "orderPrice",      # 주문가격
    "902": "remainQty",       # 미체결수량
    "910": "filledPrice",     # 체결가
    "911": "filledQty",       # 체결량
    "903": "filledAmountCum", # 체결누계금액
    "908": "time",            # 주문/체결시간 (HHMMSS)
}

# 현물잔고(type '04') 실시간 FID 맵 — 의미가 확실한 필드만 매핑 (나머지는 미확인이라 제외)
_FID_BALANCE = {
    "9001": "symbol",         # 종목코드
    "302": "name",            # 종목명
    "10": "currentPrice",     # 현재가 (부호 포함)
    "930": "quantity",        # 보유수량
    "931": "avgPrice",        # 매입단가
    "932": "purchaseAmount",  # 매입금액
    "8019": "profitRate",     # 손익율(%)
}


class _Hub:
    """SSE 구독자(asyncio.Queue) 집합. 실시간 이벤트를 전체에 fan-out."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish(self, event: dict) -> None:
        for q in list(self._subs):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)


hub = _Hub()

_task: asyncio.Task | None = None
_status: dict[str, Any] = {
    "connected": False, "lastError": None, "broker": None,
    "eventCounts": {"00": 0, "04": 0},   # 수신 카운트 (진단용: 소켓이 실제로 데이터를 받는지 확인)
    "lastEventAt": {"00": None, "04": None},
    "lastEventType": None,
}


def _normalize(values: dict) -> dict:
    """주문체결 values(FID) → 읽기 쉬운 dict."""
    out: dict[str, Any] = {}
    for fid, key in _FID.items():
        if fid in values:
            out[key] = values[fid]
    sym = str(out.get("symbol", "")).lstrip("A")
    if sym:
        out["symbol"] = sym
    for k in ("orderPrice", "filledPrice", "filledAmountCum"):
        if out.get(k):
            out[k] = str(out[k]).replace("+", "").replace("-", "").strip()
    if out.get("side"):
        out["side"] = "BUY" if "매수" in str(out["side"]) else "SELL" if "매도" in str(out["side"]) else out["side"]
    return out


def _normalize_balance(values: dict) -> dict:
    """현물잔고(04) values(FID) → 읽기 쉬운 dict (자산 실시간 갱신용)."""
    out: dict[str, Any] = {}
    for fid, key in _FID_BALANCE.items():
        if fid in values:
            out[key] = values[fid]
    sym = str(out.get("symbol", "")).lstrip("A")
    if sym:
        out["symbol"] = sym
    for k in ("currentPrice", "avgPrice", "purchaseAmount"):
        if out.get(k):
            out[k] = str(out[k]).replace("+", "").replace("-", "").strip()
    return out


async def _maybe_notify_fill(ev: dict) -> None:
    """실제 '체결'일 때만 디스코드 알림. 접수/확인 등은 무시. 이벤트 루프는 안 막음."""
    status = str(ev.get("orderStatus") or "")
    qty = str(ev.get("filledQty") or "0")
    if "체결" not in status or qty in ("", "0"):
        return
    from . import notify
    name = ev.get("name") or ev.get("symbol") or ""
    sym = ev.get("symbol") or ""
    side = "매수" if ev.get("side") == "BUY" else "매도" if ev.get("side") == "SELL" else ""
    px = ev.get("filledPrice")
    try:
        amount = int(str(px or "0")) * int(qty)
        px_s = f"{int(str(px)):,}원" if px else "-"
        amt_s = f"{amount:,}원"
    except (ValueError, TypeError):
        px_s, amt_s = str(px), "-"
    msg = f"🟢 체결 · {name} ({sym})\n{side} {qty}주 @ {px_s} · {amt_s}"
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, notify.discord, msg)   # fire-and-forget


async def _run(ws_url: str, token: str, broker: str) -> None:
    import websockets

    backoff = 1
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({"trnm": "LOGIN", "token": token}))
                async for raw in ws:
                    msg = json.loads(raw)
                    trnm = msg.get("trnm")
                    if trnm == "LOGIN":
                        if msg.get("return_code") != 0:
                            _status["lastError"] = f"LOGIN 실패: {msg.get('return_msg')}"
                            await ws.close()
                            break
                        _status["connected"] = True
                        _status["lastError"] = None
                        backoff = 1
                        # 주문체결(00) + 현물잔고(04) 실시간 등록 (item 빈값 = 내 계좌 전체)
                        await ws.send(json.dumps({
                            "trnm": "REG", "grp_no": "1", "refresh": "1",
                            "data": [{"item": [""], "type": ["00", "04"]}],
                        }))
                    elif trnm == "REG":
                        if msg.get("return_code") != 0:
                            _status["lastError"] = f"REG 실패: {msg.get('return_msg')}"
                        else:
                            _status["lastError"] = None
                    elif trnm == "PING":
                        await ws.send(raw)               # 받은 그대로 echo
                    elif trnm == "REAL":
                        from datetime import datetime, timezone, timedelta
                        now_iso = datetime.now(timezone(timedelta(hours=9))).isoformat()
                        for d in msg.get("data", []) or []:
                            t = d.get("type")
                            if t in ("00", "04"):
                                _status["eventCounts"][t] += 1
                                _status["lastEventAt"][t] = now_iso
                                _status["lastEventType"] = t
                            if t == "00":
                                ev = _normalize(d.get("values", {}) or {})
                                ev["realtimeName"] = d.get("name")
                                hub.publish({"event": "fill", "data": ev})
                                await _maybe_notify_fill(ev)
                            elif t == "04":
                                bal = _normalize_balance(d.get("values", {}) or {})
                                hub.publish({"event": "balance", "data": bal})
        except asyncio.CancelledError:
            raise
        except Exception as e:  # 연결 끊김/오류 → 지수 백오프 재연결
            _status["connected"] = False
            _status["lastError"] = str(e)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


def start() -> None:
    """키움이 동작 가능하면 실시간 체결 ws 태스크 시작 (앱 lifespan 에서 호출)."""
    global _task
    if _task is not None and not _task.done():
        return
    try:
        from brokers import available_brokers, get_broker
        if "kiwoom" not in available_brokers():
            return
        kw = get_broker("kiwoom")
        ws_url = kw.ws_url()           # type: ignore[attr-defined]
        token = kw.access_token()      # type: ignore[attr-defined]
    except Exception as e:
        _status["lastError"] = f"실시간 시작 실패: {e}"
        return
    _status["broker"] = "kiwoom"
    _task = asyncio.create_task(_run(ws_url, token, "kiwoom"))


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
    _status["connected"] = False


def status() -> dict:
    return dict(_status)
