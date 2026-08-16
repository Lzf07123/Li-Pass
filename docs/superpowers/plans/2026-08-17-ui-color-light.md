# UI 色彩与流动光效刷新实施计划

## Goal

给 Li&Pass 前端增加低饱和强调色板与克制的流动光效，解决「颜色单调、无动效」的用户反馈。
详见 [设计规格](../specs/2026-08-17-ui-color-light-design.md)。

## Architecture

- 前端 React 19 + Vite + Tailwind CSS 4（`@theme` 令牌 + 语义类）
- 令牌层：`frontend/src/index.css`（`:root` / `.dark` / `@layer components|utilities`）
- 工具层：`frontend/src/lib/accent.ts`（色相映射，纯函数）
- 组件层：MagicBento / LineChart / AppHeader / PillTabs / DashboardPage / AdminStatsPanel / AdminPage

## Tech Stack

- Node >= 22.14，`npm run dev/build/test/lint`
- 测试：vitest + @testing-library/react（jsdom）

## Global Constraints

- 分支：`codex/ui-color-light`；提交消息 `<type>: <中文简述>`，每个 Task 独立提交；
- 颜色/动效令牌只进 `index.css`；组件不新增硬编码 hex；
- 动效仅 transform/opacity/background-position；`prefers-reduced-motion` 全局降级；
- 语义色（success/warning/destructive）不被强调色替代；
- 不触碰后端、API、CSP 与认证链路。

## Task 1：令牌与动效基础设施

### Create

- 无

### Modify

- `frontend/src/index.css`：
  - `:root` / `.dark` 新增 `--portal-accent-{cyan,teal,indigo,violet,amber,rose}` 与
    `--portal-accent-*-soft`、`--portal-secondary`、`--portal-secondary-soft`；
  - `@theme` 映射 `--color-accent-*` / `--color-secondary`；
  - components 层新增 `.flow-rule`、`.aurora-soft`、`.btn-primary::after` 扫光；
  - utilities 层新增 `@keyframes btn-sheen`、`flow-line-shift`；`.card-signature` 描边流动；
- `frontend/src/components/PillTabs.css`：`.pill-tab.is-active::after` 复用 `btn-sheen`；
- `frontend/src/components/AppHeader.tsx`：底部 `flow-rule` 流光线（`aria-hidden`）。

### Test

- 现有 vitest 全量通过（不新增断言：纯 CSS 无法在 jsdom 验证视觉）。

### 验收

- [ ] `npx tsc -b && npm run lint && npm test` 绿
- [ ] `npm run build` 产物含新增令牌类名

## Task 2：accent 工具与 MagicBento 多色支持

### Create

- `frontend/src/lib/accent.ts`：`AccentKey` 六色相枚举、`accentFor(id: string): AccentKey`（稳定哈希）、
  `ACCENT_CLASSES: Record<AccentKey, { tile: string; text: string }>`；
- `frontend/src/__tests__/accent.test.ts`：确定性 + 分布 + 类名存在性。

### Modify

- `frontend/src/components/bits/MagicBento.tsx`：`MagicBentoItem` 新增可选
  `accent?: { rgb: string; hex: string }`；卡片 style 注入 `--glow-color` / `--bento-label`；
- `frontend/src/components/bits/MagicBento.css`：标签底色与图标色改由 `var(--glow-color)` /
  `var(--bento-label)` 派生，保留网格级默认值。

### Test

- `frontend/src/__tests__/MagicBento.test.tsx`：新增「item 级 accent 覆盖卡片颜色变量」用例。

### 验收

- [ ] 红→绿：先补测试再实现；`npm test` 绿

## Task 3：页面落地

### Modify

- `frontend/src/pages/DashboardPage.tsx`：
  - 头像占位与应用图标占位瓦片用 `accentFor` 着色；
  - 各分区图标按固定色相分层（基本资料 cyan、邮箱 indigo、密码 amber、手机 teal、
    登录安全 violet、会话 cyan、可信设备 teal、应用广场 rose）；
  - 分区标题下加 `.flow-rule`；页面根加 `AuroraBackground`（`.aurora-soft`）；
- `frontend/src/pages/AdminPage.tsx`：页面根加 `AuroraBackground`（`.aurora-soft`，更低浓度）；
- `frontend/src/pages/AdminStatsPanel.tsx`：
  - `overviewCards` 每张卡带 `accent`（rgb+hex，六色相各一）；
  - `StatSparkline` 面积用 `fillOpacity` + `var(--bento-label)`；
  - 认证方式分布条按 `AUTH_METHOD_COLORS`（password cyan / email_otp teal / totp violet /
    recovery amber）着色；
  - 趋势图系列色改为多色相；
- `frontend/src/components/charts/LineChart.tsx`：`DEFAULT_COLORS` 扩为六色相循环。

### Test

- 现有 `DashboardPage` / `AdminStatsPanel` / `LineChart` 测试保持绿；必要时只改文案无关断言。

### 验收

- [ ] `npx tsc -b && npm run lint && npm test && npm run build` 全绿
- [ ] 截图检查（Task 4）

## Task 4：验证、文档与收尾

### Modify

- `CHANGELOG.md`「未发布（开发中）」→ 功能 分区追加 UI 刷新条目；
- `design-system/lipass/MASTER.md`：令牌表 + 组件规格补强调色板与流动光效；
- `design-system/lipass/BRAND.md`：3.1 色彩系统补「支撑强调色板」小节与用色规则；
  第 8 章差距表补一条状态；

### 验收

- [ ] 前端 CI 顺序命令全绿；
- [ ] dev server + 浏览器截图：登录（浅/深）、用户中心、管理后台统计；
- [ ] 分支提交历史与文档一致，合并回 main。
