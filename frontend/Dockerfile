ARG IMAGE_REGISTRY=
FROM ${IMAGE_REGISTRY}node:20-alpine AS build
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ${IMAGE_REGISTRY}nginx:1.27-alpine
ENV CONNECT_SRC=http://localhost:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
