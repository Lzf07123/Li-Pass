ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}python:3.12-slim

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN chown -R 10001:10001 /app
USER 10001
EXPOSE 3001
CMD ["python", "app.py"]
