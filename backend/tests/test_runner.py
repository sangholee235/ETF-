"""runner.run_once 의 '오늘 현금부족 SKIP 억제' 관련 회귀 테스트.

과거 버그: 현금부족으로 한 번 SKIP하면 그날 남은 tick을 전부 조용히
건너뛰어서, 낮에 입금이 들어와도 당일에는 절대 못 알아챘음(다음날까지
대기). 지금은 매 tick마다 다시 계산하고, 로그만 중복 안 남긴다.
"""

import pytest

from app.bot import config as config_module
from app.bot import state as state_module
from app.bot.runner import _summary, run_once
from app.bot.config import BotConfig
from app.bot.state import BotState
from tests.conftest import FakeClient


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """실제 backend/data/ 를 건드리지 않도록 BotConfig/BotState 저장 경로를 임시 디렉터리로."""
    monkeypatch.setattr(config_module, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(state_module, "_DATA_DIR", tmp_path)
    yield


def _cfg():
    return BotConfig(
        portfolio=[{"symbol": "069500", "name": "KODEX 200", "weight": 100}],
        daily_budget_krw=100_000,
        dry_run=True,
    )


def test_summary_does_not_crash_on_empty_logs():
    """예전엔 logs=[] 로 호출되면 logs[-1] 에서 IndexError 가 났음."""
    r = _summary(_cfg(), BotState(), [])
    assert r["decision"]["action"] == "SKIP"
    assert r["symbol"] is None


def test_cash_short_skip_is_deduplicated_but_not_blocked():
    _cfg().save()  # kiwoom 브로커용 설정 파일을 임시 디렉터리에 미리 기록
    # 매수가능금액이 1주(30,000원) 값도 안 되는 상황
    poor_client = FakeClient(buying_power=100, last_price=30_000)

    r1 = run_once(client=poor_client, broker="kiwoom")
    assert r1["decision"]["action"] == "SKIP"

    # 같은 날 두 번째 tick — 여전히 돈 없음. 로그는 중복 안 남지만 크래시도 안 나야 함
    # (예전 버그: cash_exhausted_date 억제 분기가 logs=[] 로 _summary 를 불러 IndexError).
    r2 = run_once(client=poor_client, broker="kiwoom")
    assert r2["decision"]["action"] == "SKIP"

    # 낮에 입금이 들어온 상황을 흉내: 매수가능금액이 충분해진 새 클라이언트로 재시도.
    # cash_exhausted_date가 오늘로 찍혀있어도, 이제는 매 tick 다시 계산하므로 즉시 매수돼야 한다.
    rich_client = FakeClient(buying_power=10_000_000, last_price=30_000)
    r3 = run_once(client=rich_client, broker="kiwoom")
    assert r3["decision"]["action"] == "MARKET_BUY"

    # 매수 성공 시 억제가 해제됐는지 상태 파일로도 확인.
    saved = BotState.load("kiwoom")
    assert saved.cash_exhausted_date is None
