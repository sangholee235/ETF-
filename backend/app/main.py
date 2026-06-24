"""FastAPI 진입점.

실행 (backend 디렉터리에서):
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

문서: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import sys
from pathlib import Path

# backend/ 를 import 경로에 추가 -> `import tossapi`, `import app...` 동작
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.routers import account, market, orders  # noqa: E402

app = FastAPI(title="Tossapi Backend", version="0.1.0")

# Vite 개발 서버(기본 5173)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(account.router)
app.include_router(orders.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
