ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}node:22-alpine AS build
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
WORKDIR /app
COPY package*.json ./
# 复用 BuildKit 的 npm 缓存卷（跨构建共享），并跳过 audit/fund 的网络往返
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM ${IMAGE_REGISTRY}nginx:1.27-alpine
ENV CONNECT_SRC=http://localhost:8000 \
    TZ=Asia/Shanghai
RUN apk add --no-cache tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
