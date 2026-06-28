"""키움 일봉차트 TR 응답 구조 탐색 (읽기 전용, 안전).
ka10081(주식일봉차트조회요청) /api/dostk/chart 후보를 호출해 키/필드명을 덤프한다.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", ".env"))

from brokers.kiwoom import KiwoomBroker

b = KiwoomBroker()
data = b._request(
    "ka10081",
    "/api/dostk/chart",
    body={"stk_cd": "069500", "base_dt": "", "upd_stkpc_tp": "1"},
)
# 최상위 키
print("TOP KEYS:", list(data.keys()))
# 리스트로 보이는 키 찾기
for k, v in data.items():
    if isinstance(v, list):
        print(f"\nLIST KEY: {k}  (len={len(v)})")
        if v:
            print("FIRST ITEM:", json.dumps(v[0], ensure_ascii=False, indent=2))
            print("LAST ITEM:", json.dumps(v[-1], ensure_ascii=False, indent=2))
