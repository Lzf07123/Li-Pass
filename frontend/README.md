# Li&Pass 前端（frontend）

React + Vite + TypeScript + Tailwind CSS 构建的统一登录门户 SPA：登录/注册（含邀请注册）、找回/重置密码、邮箱验证、授权确认、用户中心（资料/头像/密码/会话/账号注销；手机绑定界面暂未开放）、应用广场与管理后台。

## 本地开发

```bash
npm install
cp src/lib/brand.example.ts src/lib/brand.ts        # 品牌配置示例（brand.ts 已 gitignore）
cp .env.example .env                                # 按需取消注释 VITE_API_BASE_URL
export VITE_API_BASE_URL=http://localhost:8000   # 直连后端，不内置代理
npm run dev
```

开发服务器默认运行在 http://localhost:5173 （Vite 默认端口，与 nginx 生产容器一致）。

容器热更新：在仓库根目录执行
`docker compose -f docker-compose.yaml -f docker-compose.dev.yaml --profile bundle up -d --build`，
前端由容器内 Vite dev server 提供 HMR（经单域名网关透传 WebSocket；容器内以轮询监听源码变化，
由 `VITE_WATCH_POLLING=true` 控制）。

项目内 `.npmrc` 已把 npm 源指向 `https://registry.npmmirror.com/`（国内加速；USTC 的 npm 镜像已停服并重定向到该源），Docker 构建与本地 `npm ci` 均生效。海外网络或 CI 如遇镜像不可达，可临时用 `npm config set registry https://registry.npmjs.org/` 覆盖。

## 脚本

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | Vite 开发服务器（HMR） |
| `npm run build` | 类型检查 + 生产构建（`tsc -b && vite build`，产物在 `dist/`） |
| `npm run preview` | 本地预览构建产物 |
| `npm run lint` | oxlint 检查 |
| `npm test` | Vitest 单元测试（测试目录仅保留本地，不入库） |

## 与后端 / 部署的关系

- 浏览器通过 `VITE_API_BASE_URL` 直连后端 API（`.env.example` 为注释模板：同源网关部署留空，本地直连填 `http://localhost:8000`）；会话 Cookie 由后端域名签发。
- 品牌与站点信息（应用名、备案文案、页脚链接等）由 `src/lib/brand.ts` 统一读取 `VITE_APP_NAME` / `VITE_APP_TAGLINE` / `VITE_ICP_FILING_*` / `VITE_POLICE_FILING_*` / `VITE_FOOTER_LINKS` 构建期环境变量，未设置时使用内置默认值；变量示例见 `.env.example`，容器构建经 compose 的同名 build args 注入。仓库只提交 `src/lib/brand.example.ts`，本地先 `cp src/lib/brand.example.ts src/lib/brand.ts`（brand.ts 已 gitignore、可按部署就地修改；CI 会自动执行该复制）。
- 生产镜像为多阶段构建（见 `Dockerfile`）：`node:22-alpine` 构建静态产物（`engines` 要求 Node ≥22.14），`nginx:1.27-alpine` 托管并注入安全响应头与 CSP（见 `nginx.conf.template`），端口固定 5173。
- `npm ci` 构建层启用了 BuildKit 的 npm 缓存挂载并跳过 audit/fund，重建时复用依赖缓存；首次构建仍会完整下载依赖。
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
