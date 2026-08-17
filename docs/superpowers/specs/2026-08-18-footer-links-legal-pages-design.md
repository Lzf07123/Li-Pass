# 页脚丰富化与法律页面设计

日期：2026-08-18
状态：已确认，进入实施

## 目标

丰富全站页脚：新增 GitHub 仓库、GitHub Issues 反馈入口、公开联系邮箱、隐私政策与服务条款链接；新增 `/privacy`、`/terms` 两个静态法律页面。

所有新增内容均由构建期环境变量驱动：**变量填写才显示，置空自动隐藏**，避免出现占位假链接。

## 现状与约束

- 页脚组件 `frontend/src/components/SiteFooter.tsx` 目前只有版权 + ICP/公安备案 + `VITE_FOOTER_LINKS` 数组（默认空）。
- 品牌配置集中在前端 `frontend/src/lib/brand.example.ts`（复制为 gitignored 的 `brand.ts`），通过 `VITE_*` 注入，ICP/公安备案已实现「空值隐藏」。
- README 已公开仓库 `https://github.com/Lzf07123/Li-Pass`；公开联系邮箱由用户确认为 `18312052639@163.com`。
- 设计规范（`design-system/lipass/BRAND.md`）：页脚 12px、`text-muted`、`border-t border-border/60`、`bg-surface/60`、居中排布。
- 路由为 React Router 7，`AppRoutes` 在 `frontend/src/App.tsx`，支持懒加载。

## 方案与取舍

### 新增品牌变量

| 变量 | 默认值 | 空值行为 |
| --- | --- | --- |
| `VITE_GITHUB_URL` | `https://github.com/Lzf07123/Li-Pass` | 隐藏 GitHub 链接 |
| `VITE_GITHUB_ISSUES_URL` | `${GITHUB_URL}/issues` | 隐藏「反馈问题」链接 |
| `VITE_LICENSE_NAME` / `VITE_LICENSE_URL` | `Apache-2.0` / `${GITHUB_URL}/blob/main/LICENSE` | 任一置空隐藏开源协议入口 |
| `VITE_CONTACT_EMAIL` | `18312052639@163.com` | 隐藏「联系我们」链接 |
| `VITE_FOOTER_LINKS` | `[{"label":"隐私政策","href":"/privacy"},{"label":"服务条款","href":"/terms"}]` | 隐藏整组附加链接 |

取舍：默认值直接填公开仓库与用户确认的公开邮箱，保证开箱即用；任何部署方可通过置空 `VITE_*` 关闭对应入口。隐私/服务条款页面始终存在，但页脚链接是否展示由 `VITE_FOOTER_LINKS` 决定。

### 页脚结构

- 全站统一由 `SiteFooter` 渲染同一响应式页脚，不再区分「完整版/紧凑版」：移动端版权/备案与链接混排为单行流式自动换行，桌面端（`sm+`）居中两行（上为链接导航、下为版权/备案）；小字、弱化色、半透明表面与 1px 分隔线保持一致。
- 认证页（`AuthShell`）与已登录页/法律页共用该页脚；加载骨架（`AuthSkeleton`/`PageSkeleton`）按同一形态对齐，避免加载前后形态跳变。
- 内部路径（`/privacy`、`/terms`）用 React Router `Link`，外部链接一律 `target="_blank" rel="noreferrer"`。
- GitHub 图标使用内联 SVG，不新增图标库依赖。

### 法律页面

- 新增 `frontend/src/pages/LegalPage.tsx`，按 `kind` 渲染隐私政策或服务条款。
- 布局：`AppHeader`（标题 + 返回首页）+ 居中 `max-w-3xl` 卡片正文 + `SiteFooter`；不要求登录。
- 内容覆盖：隐私政策（收集信息、用途、共享、Cookie、安全、保留、用户权利、未成年人、变更、联系）；服务条款（服务说明、账号责任、可接受使用、第三方网站、知识产权、免责、终止、变更、法律适用、联系）。

## 接口 / 数据模型

无后端接口、数据库或 OIDC 契约变更。仅前端新增两个静态路由。

## 安全影响

- 不触碰认证、会话、令牌、限流与审计逻辑。
- 外部链接统一 `rel="noreferrer"`，不向第三方泄露来源页。
- 公开邮箱与仓库地址为用户确认公开信息，非秘密。
- 法律页面不加载任何用户数据，无 CSRF/注入面。

## UI 设计

遵循 `design-system/lipass/BRAND.md`：页脚 12px 弱化文字、半透明表面、1px 分隔线；法律页正文使用 `card` 容器，标题层级清晰，深浅色主题沿用现有令牌，无新增动效。

## 验收标准

- `VITE_GITHUB_URL`、`VITE_GITHUB_ISSUES_URL`、`VITE_CONTACT_EMAIL`、`VITE_FOOTER_LINKS` 任一为空时对应入口隐藏。
- `/privacy`、`/terms` 可直接访问，页面含完整章节与联系邮箱。
- `frontend` 全量验证通过：`npx tsc -b && npm run lint && npm test && npm run build`。
- CHANGELOG 与部署文档环境变量表同步。

## 风险

- 法律文本为通用模板，非律师出具；后续如有主体公司信息需更新「联系我们」章节。
- `brand.ts` 为本地 gitignored 副本，改动需同步 `brand.example.ts` 与 `.env.example`，否则新克隆环境缺失配置说明。
