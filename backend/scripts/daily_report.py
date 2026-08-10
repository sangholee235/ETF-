#!/usr/bin/env python3
"""장 마감 후 하루치 실행기록을 마크다운으로 정리해 별도 git 리포에 커밋·push한다.

이 프로젝트의 "예측하지 않는다" 철학 그대로 — LLM 없이, 상태 파일(JSON)의
로그를 그대로 파싱해서 결정론적으로 문서를 만든다. 서버 호스트에서
(컨테이너 밖에서) 돌리는 걸 전제로 한다 — docker volume 경로를 직접 읽고,
git push는 이 리포 전용 Deploy Key만 쓰는 별도 리포로 나간다(메인 앱
리포와는 완전히 분리 — 여기 자격증명이 털려도 메인 코드는 못 건드림).

사용법 (서버 크론탭에서 매일 장 마감 후 1회):
    sudo python3 daily_report.py

환경별로 경로가 다르면 아래 상수만 바꾸면 된다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BOT_DATA_ROOT = Path("/var/lib/docker/volumes/tossapi_bot_data/_data")
CONFIG_DIR = BOT_DATA_ROOT               # bot_config_{broker}.json — 최상위
STATE_DIR = BOT_DATA_ROOT / "data"       # bot_state_{broker}.json — data/ 하위
LOG_REPO_DIR = Path("/home/ubuntu/ETF-bot-daily-log")
BROKERS = ["kiwoom", "toss"]
BROKER_LABEL = {"kiwoom": "키움증권", "toss": "토스증권"}
KST = timezone(timedelta(hours=9))

ACTION_LABEL = {
    "MARKET_BUY": "매수",
    "LIMIT_BUY": "매수(지정가)",
    "SKIP": "SKIP",
}

_PRICE_IN_REASON = re.compile(r"([\d,]+)원")


def price_from_log(lg: dict) -> int | None:
    """시장가 매수는 OrderLog.price가 항상 None(체결 전 미확정)이라, runner.py가
    reason 문자열에 남겨둔 '{가격:,}원 기준' 패턴에서 실제 사용된 가격을 복원한다."""
    if lg.get("price"):
        return int(lg["price"])
    m = _PRICE_IN_REASON.search(lg.get("reason") or "")
    return int(m.group(1).replace(",", "")) if m else None


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_real_progress(broker: str) -> list[dict] | None:
    """실계좌 보유현황 기준 목표비중 진행률 — 대시보드(/api/bot/preview)가 이미 검증해
    쓰는 계산을 그대로 재사용한다(호스트에서 별도 재구현하면 값이 어긋날 위험이 있음).
    state.portfolio_invested(봇 자체 장부)는 봇이 추적 시작한 시점 이후 매수만 누적된
    값이라 실제 계좌 비중과 다를 수 있어 여기 쓰면 안 됨(실제로 이 차이 때문에
    "나스닥100이 실제론 압도적으로 많은데 왜 33%로 뜨냐"는 오류를 겪었음).
    컨테이너 밖(호스트)에서 돌기 때문에 docker exec로 컨테이너 내부 API를 호출한다."""
    code = (
        "import urllib.request, json; "
        f"print(json.dumps(json.load(urllib.request.urlopen("
        f"'http://127.0.0.1:8000/api/bot/preview?broker={broker}'))['progress']))"
    )
    try:
        out = subprocess.run(
            ["docker", "exec", "tossapi-backend-1", "python3", "-c", code],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return json.loads(out.stdout)
    except Exception as e:
        print(f"실계좌 비중 조회 실패({broker}): {e}", file=sys.stderr)
        return None


def broker_section(broker: str, today: str) -> str:
    state = load_json(STATE_DIR / f"bot_state_{broker}.json")
    config = load_json(CONFIG_DIR / f"bot_config_{broker}.json")
    label = BROKER_LABEL.get(broker, broker)

    if not state:
        return f"## {label}\n\n상태 파일 없음(미사용 브로커).\n"

    logs_today = [lg for lg in state.get("logs", []) if lg.get("trade_date") == today]
    buys = [lg for lg in logs_today if lg.get("action") in ("MARKET_BUY", "LIMIT_BUY")]
    skips = [lg for lg in logs_today if lg.get("action") == "SKIP"]
    spent = sum((price_from_log(lg) or 0) * (lg.get("quantity") or 0) for lg in buys)

    lines = [f"## {label}", ""]
    lines.append("### 요약")
    lines.append(f"- 오늘 매수: {len(buys)}건 (총 {spent:,}원)")
    lines.append(f"- SKIP: {len(skips)}건")
    lines.append("")

    # 목표비중 달성 현황 — 반드시 실계좌 보유현황 기준(fetch_real_progress). 실패 시에만
    # state.portfolio_invested(봇 자체 장부)로 폴백하되, 부정확할 수 있음을 표로 명시.
    portfolio = (config or {}).get("portfolio") or []
    items = [p for p in portfolio if p.get("symbol") and float(p.get("weight", 0)) > 0]
    real_progress = fetch_real_progress(broker)

    total_w = sum(float(p["weight"]) for p in items) or 1.0
    if items and real_progress is not None:
        by_symbol = {p["symbol"]: p for p in real_progress}
        lines.append("### 목표비중 달성 현황 (실계좌 보유현황 기준)")
        lines.append("| 종목 | 목표비중 | 현재비중 | 차이 |")
        lines.append("|---|---|---|---|")
        for p in items:
            rp = by_symbol.get(p["symbol"])
            target = float(p["weight"]) / total_w * 100
            current = rp["currentWeight"] * 100 if rp else 0.0
            gap = target - current
            sign = "부족" if gap > 0 else "초과"
            lines.append(
                f"| {p.get('name', p['symbol'])} ({p['symbol']}) | {target:.1f}% | "
                f"{current:.1f}% | {abs(gap):.1f}%p {sign} |"
            )
        lines.append("")
    elif items:
        # 실계좌 조회 실패(컨테이너 재시작 중 등) — 부정확할 수 있는 값임을 표에서부터 밝힘
        invested = state.get("portfolio_invested") or {}
        total_inv = sum(float(invested.get(p["symbol"], 0)) for p in items) or 1.0
        lines.append("### 목표비중 달성 현황 (⚠️ 실계좌 조회 실패 — 봇 자체 장부 기준, 부정확할 수 있음)")
        lines.append("| 종목 | 목표비중 | 현재비중(추정) | 차이 |")
        lines.append("|---|---|---|---|")
        for p in items:
            target = float(p["weight"]) / total_w * 100
            current = float(invested.get(p["symbol"], 0)) / total_inv * 100
            gap = target - current
            sign = "부족" if gap > 0 else "초과"
            lines.append(
                f"| {p.get('name', p['symbol'])} ({p['symbol']}) | {target:.1f}% | "
                f"{current:.1f}% | {abs(gap):.1f}%p {sign} |"
            )
        lines.append("")

    if logs_today:
        lines.append("### 오늘 실행 로그")
        lines.append("| 시각 | 액션 | 종목 | 수량 | 가격 | 사유 |")
        lines.append("|---|---|---|---|---|---|")
        for lg in logs_today:
            ts = (lg.get("ts") or "")[11:16]  # HH:MM
            action = ACTION_LABEL.get(lg.get("action"), lg.get("action"))
            sym = lg.get("symbol") or "-"
            qty = lg.get("quantity") or 0
            price = price_from_log(lg)
            price_s = f"{price:,}원" if price else "-"
            reason = (lg.get("reason") or "").replace("|", "/")
            lines.append(f"| {ts} | {action} | {sym} | {qty} | {price_s} | {reason} |")
        lines.append("")
    else:
        lines.append("오늘 실행 기록 없음.\n")

    return "\n".join(lines)


def update_index(log_repo: Path, date_str: str) -> None:
    """README.md 맨 위에 오늘 날짜 링크를 추가(최신순)."""
    readme = log_repo / "README.md"
    header = "# ETF 자동 적립 봇 — 일일 로그\n\n서버가 장 마감 후 매일 자동으로 기록합니다.\n\n## 최근 기록\n"
    entry = f"- [{date_str}](logs/{date_str}.md)\n"

    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        if "## 최근 기록" in text:
            before, _, after = text.partition("## 최근 기록\n")
            # 같은 날짜 재실행 시 중복 라인 방지
            after_lines = [l for l in after.splitlines(keepends=True) if date_str not in l]
            new_text = before + "## 최근 기록\n" + entry + "".join(after_lines)
        else:
            new_text = text.rstrip() + "\n\n## 최근 기록\n" + entry
    else:
        new_text = header + entry

    readme.write_text(new_text, encoding="utf-8")


def main() -> None:
    now = datetime.now(KST)
    today = now.date().isoformat()
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]

    sections = [f"# {today} ({weekday_kr}) 실행 기록\n"]
    for broker in BROKERS:
        sections.append(broker_section(broker, today))

    LOG_REPO_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_REPO_DIR / "logs").mkdir(exist_ok=True)
    out_path = LOG_REPO_DIR / "logs" / f"{today}.md"
    out_path.write_text("\n".join(sections), encoding="utf-8")
    update_index(LOG_REPO_DIR, today)

    def run(cmd: list[str]) -> None:
        subprocess.run(cmd, cwd=LOG_REPO_DIR, check=True)

    run(["git", "add", "-A"])
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=LOG_REPO_DIR)
    if diff.returncode == 0:
        print("변경 없음 — 커밋 생략")
        return
    run(["git", "commit", "-m", f"docs: {today} 실행 기록"])
    run(["git", "push", "origin", "HEAD"])
    print(f"완료: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 크론에서 조용히 실패해도 로그(journalctl)에는 남게
        print(f"daily_report 실패: {e}", file=sys.stderr)
        sys.exit(1)
