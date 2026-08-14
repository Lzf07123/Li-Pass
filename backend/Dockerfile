ARG IMAGE_REGISTRY=
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple
FROM ${IMAGE_REGISTRY}python:3.12-slim
# FROM 之前声明的 ARG 仅在 FROM 中可用，构建阶段需重新声明才能引用。
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple

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
RUN pip install --no-cache-dir --no-compile \
        -i "${PIP_INDEX_URL}" \
        -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts ./scripts
# ip2region Python 绑定与 xdb 数据均随仓库入库（v3.17.0，SHA256 已固定），
# 构建期直接 COPY、不再联网下载；运行时仍可在站点设置中手动/自动更新。
COPY ip2region ./ip2region
COPY data/ip2region ./data/ip2region
# 构建期冒烟检查：镜像内必须能完整导入应用（含全部路由与 vendored 依赖），
# 把“遗漏 COPY 模块”这类问题前移到镜像构建阶段暴露。
RUN python -c "import app.main"

RUN mkdir -p /app/keys /app/uploads && chown -R 10001:10001 /app

USER 10001

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\" --workers \"${UVICORN_WORKERS:-1}\" --limit-max-requests 10000"]
