ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 统一容器时区为 Asia/Shanghai（日志与本地时间一致）
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY requirements.txt .
# --no-compile：镜像内不写 .pyc，配合 PYTHONDONTWRITEBYTECODE 让镜像更小。
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts ./scripts

RUN mkdir -p /app/keys /app/uploads && chown -R 10001:10001 /app

USER 10001

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --workers \"${UVICORN_WORKERS:-1}\" --limit-max-requests 10000"]
