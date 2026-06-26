# 토스 적립봇 백엔드 (FastAPI + 봇 + 스케줄러)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TOSSAPI_DATA_DIR=/appdata

WORKDIR /app

# 의존성 먼저 (레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY tossapi/ ./tossapi/
COPY app/ ./app/

# 상태/설정 보관 디렉터리 (볼륨 마운트 지점)
RUN mkdir -p /appdata/data

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
