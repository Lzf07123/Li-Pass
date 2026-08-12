# Portal OSS 前端（frontend）

React + Vite + TypeScript + Tailwind CSS 构建的统一登录门户 SPA：登录/注册、找回/重置密码、授权确认、用户中心（资料/头像/手机/密码/会话）、应用广场与管理后台。

## 本地开发

```bash
npm install
export VITE_API_BASE_URL=http://localhost:8000   # 直连后端，不内置代理
npm run dev
```

开发服务器默认运行在 http://localhost:5173 （Vite 默认端口，与 nginx 生产容器一致）。

## 脚本

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | Vite 开发服务器（HMR） |
| `npm run build` | 类型检查 + 生产构建（`tsc -b && vite build`，产物在 `dist/`） |
| `npm run preview` | 本地预览构建产物 |
| `npm run lint` | oxlint 检查 |
| `npm test` | Vitest 单元测试（测试目录仅保留本地，不入库） |

## 与后端 / 部署的关系

- 浏览器通过 `VITE_API_BASE_URL`（默认 http://localhost:8000）直连后端 API；会话 Cookie 由后端域名签发。
- 生产镜像为多阶段构建（见 `Dockerfile`）：`node:20-alpine` 构建静态产物，`nginx:1.27-alpine` 托管并注入安全响应头与 CSP（见 `nginx.conf.template`），端口固定 5173。
- CSP 的 `connect-src` / `img-src` 由 compose 的 `CONNECT_SRC`（即 `VITE_API_BASE_URL`）注入，后端托管的头像（`/uploads/avatars`）可跨源正常加载。

## 目录结构

```text
src/
├── api/          # API 客户端与类型定义
├── components/   # Brand、AuthShell、AppHeader、ThemeToggle 等公共组件
├── hooks/        # useTheme 等自定义 Hook
├── pages/        # 各业务页面（登录、注册、用户中心、管理后台等）
└── main.tsx / App.tsx / index.css
```
