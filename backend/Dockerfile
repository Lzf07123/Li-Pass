ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}python:3.12-slim

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

RUN mkdir -p /app/keys /app/uploads && chown -R 10001:10001 /app

USER 10001

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --limit-max-requests 10000"]
