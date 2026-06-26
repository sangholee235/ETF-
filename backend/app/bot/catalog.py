"""클릭 선택용 주요(대형) ETF 카탈로그.

tax: 'exempt'  = 국내주식형, 일반계좌도 매매차익 비과세
     'taxed'   = 국내상장 해외/기타 ETF, 매매차익 15.4% 과세(ISA면 유리)
"""

from __future__ import annotations

MAJOR_ETFS: list[dict] = [
    {"symbol": "069500", "name": "KODEX 200", "category": "국내지수", "tax": "exempt"},
    {"symbol": "102110", "name": "TIGER 200", "category": "국내지수", "tax": "exempt"},
    {"symbol": "229200", "name": "KODEX 코스닥150", "category": "국내지수", "tax": "exempt"},
    {"symbol": "360750", "name": "TIGER 미국S&P500", "category": "미국지수", "tax": "taxed"},
    {"symbol": "379800", "name": "KODEX 미국S&P500", "category": "미국지수", "tax": "taxed"},
    {"symbol": "133690", "name": "TIGER 미국나스닥100", "category": "미국지수", "tax": "taxed"},
    {"symbol": "381180", "name": "TIGER 미국필라델피아반도체나스닥", "category": "테마", "tax": "taxed"},
    {"symbol": "449180", "name": "TIGER 미국배당다우존스", "category": "배당", "tax": "taxed"},
]
