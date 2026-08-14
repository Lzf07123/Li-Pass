ARG IMAGE_REGISTRY=
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple
FROM ${IMAGE_REGISTRY}python:3.12-slim
# FROM 之前声明的 ARG 仅在 FROM 中可用，构建阶段需重新声明才能引用。
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple

ENV TZ=Asia/Shanghai
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir \
        -i "${PIP_INDEX_URL}" \
        -r requirements.txt
COPY app.py .
RUN chown -R 10001:10001 /app
USER 10001
EXPOSE 3001
CMD ["python", "app.py"]
