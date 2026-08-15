# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.
>
> **品牌层：** 品牌定位、设计总思路、视觉识别与「环境呼吸感」氛围动效标准见 [BRAND.md](./BRAND.md)。
> 先遵循 BRAND.md 的品牌意图，再按本文件落地令牌与组件规格。

---

**Project:** Li&Pass
**Generated:** 2026-08-12 10:23:37
**Updated:** 2026-08-13（与 `frontend/src/index.css`、`frontend/src/components/` 对齐）
**Category:** SSO 统一登录门户（Li&Pass）

> **来源声明：** 本文件描述当前前端实现使用的视觉系统；最终以 `frontend/src/index.css` 的
> Tailwind CSS 4 `@theme` 令牌与组件代码为准，本文件仅作设计约定速览。

---

## Global Rules

### 色彩

令牌定义在 `frontend/src/index.css` 的 `:root`（浅色）与 `.dark`（深色）中，组件通过
`bg-primary / text-muted / border-border` 等 Tailwind 语义类引用。

| 角色 | 浅色 | 深色 | Tailwind 令牌 |
| --- | --- | --- | --- |
| 背景 | `#F8FAFC` | `#0B1220` | `bg-background` |
| 表面 | `#FFFFFF` | `#111A2C` | `bg-surface` |
| 表面 2 | `#F1F5F9` | `#1B2740` | `bg-surface-2` |
| 前景 | `#0F172A` | `#E2E8F0` | `text-foreground` |
| 弱化文本 | `#64748B` | `#94A3B8` | `text-muted` |
| 边框 | `#E2E8F0` | `#263449` | `border-border` |
| 主色 | `#0369A1` | `#38BDF8` | `bg-primary / text-primary` |
| 主色悬停 | `#075985` | `#7DD3FC` | `hover:bg-primary-hover` |
| 主色前景 | `#FFFFFF` | `#082F49` | `text-primary-foreground` |
| 成功 | `#15803D` | `#4ADE80` | `text-success / bg-success-soft` |
| 警告 | `#B45309` | `#FBBF24` | `text-warning / bg-warning-soft` |
| 危险 | `#DC2626` | `#F87171` | `text-destructive / bg-destructive-soft` |
| 焦点环 | `#0369A1` | `#38BDF8` | `focus:ring-primary/20` |

**色彩说明：** 安全蓝 + 中性石板灰（Trust & Authority / Minimalism）；前景/背景对比满足
WCAG AA（正文 ≥ 4.5:1）。深色模式使用去饱和浅色调变体，而非简单反色。

### 字体

- **字体栈：** `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`
- **加载方式：** 不内置远程字体引用，优先使用系统/本机 Inter，未安装时回退系统字体。
- **字号：** 正文 `14px`（`text-sm`），页面标题 `22px`（认证页），头部 `15px`，弱化说明 `12px`（`text-xs`）。

### 间距与圆角

- 间距使用 Tailwind 默认刻度（4px 基准）：`p-2`（8px）、`p-3`（12px）、`p-4`（16px）、`p-5`（20px）、`p-6`（24px）、`p-8`（32px）。
- 圆角：按钮/输入框 `rounded-lg`（8px），卡片/弹窗 `rounded-2xl`（16px），徽章 `rounded-full`。

### 阴影与动效

| Token | 值 |
| --- | --- |
| `--shadow-sm` | `0 0.6px 1.8px rgba(15,23,42,0.02), 0 2.4px 7.2px rgba(15,23,42,0.04)` |
| `--shadow-md` | 在 `sm` 上叠加 `0 8px 24px rgba(15,23,42,0.06)` |
| `--shadow-lg` | 在 `md` 上叠加 `0 8px 32px rgba(15,23,42,0.08)` |
| `--ease-out` | `cubic-bezier(0.25, 0.1, 0.25, 1)`（入场） |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)`（按压/弹窗） |
| 时长 | `--motion-fast: 150ms`、`--motion-base: 250ms`、`--motion-slow: 350ms` |

交互统一：可点击元素必须有 `cursor-pointer`；hover 轻微上移（`translateY(-1px)`），按压 `scale(0.97)`；
`prefers-reduced-motion: reduce` 时所有动画缩短为 `0.01ms` 并保持单帧。

---

## Component Specs（对应 `frontend/src/components/` 与 `index.css`）

### 按钮（`.btn` 系列）

- `.btn-primary`：主色 → 主色悬停的纵向渐变背景 + 主色前景；hover 渐变下移并抬升阴影（`background-position` 过渡）。
- `.btn-secondary`：透明/表面背景 + 边框；hover 换 `surface-2`。
- `.btn-danger`：危险色背景 + 白色前景；hover 透明度降低。
- `.btn-ghost` / `.btn-link`：弱化/文字按钮，用于次要操作。
- 统一圆角 `rounded-lg`、`px-4 py-3`、`text-sm font-medium`，`disabled` 时 `opacity-50` 且不可点击。

### 卡片（`.card`）

- `bg-surface` + `border-border` + `rounded-2xl` + 弥散阴影。
- hover：`translateY(-1px)` 并切换 `--shadow-lg`；交互式卡片加 `.card-interactive`。
- `.card-signature`：认证页专用，叠加于 `.card` 之上，以蓝→青→紫低透明度渐变替代描边（padding-box 表面 + border-box 渐变边框双背景）。

### 表单（`.label` / `.input` / `.input-sm`）

- 输入框：`bg-surface`、`rounded-lg`、`px-3 py-2.5`、`text-sm`。
- focus：主色边框 + `ring-2 ring-primary/20`；placeholder 用 `text-muted`。

### 胶囊标签（`PillTabs` / `.pill-tab`）

- 位置：`frontend/src/components/PillTabs.tsx` + `PillTabs.css`，管理后台顶部标签栏使用；基于 gsap，移植 React Bits PillNav 的圆环展开效果。
- 结构：`PillTabs` 内部渲染 `ScrollTabs`（`fadeColor="var(--portal-surface-2)"`），轨道为 surface-2 背景 + 9999px 圆角；每颗 `.pill-tab` 含 `.pill-tab-circle`（主色圆环）与 `.pill-tab-stack`（双层文案）。
- 交互：hover / 键盘聚焦时圆环从胶囊底部中心放大覆盖整颗胶囊，旧文案上滑、主色前景文案从下方滑入（进入 300ms / 离开 200ms）；活动标签固定为主色背景 + 主色前景。`prefers-reduced-motion` 下瞬切。
- 保留 ScrollTabs 的横向滑动、边缘渐隐与深链居中能力。

### Bento 展示网格（`MagicBento` / `.magic-bento-card`）

- 位置：`frontend/src/components/bits/MagicBento.tsx` + `MagicBento.css`，后台「数据统计」概览卡片使用；基于 gsap，移植 React Bits MagicBento。
- 结构：`.magic-bento` 内为 `.card-grid.bento-section`，卡片为深色表面（浅色 `#0F172A` / 深色 `#111A2C`）；首卡跨两列，`emphasize` 项数值加粗放大（tabular-nums）。
- 交互：全局光标聚光（`.global-spotlight`）、悬停粒子星点、边框辉光（`--glow-*` 变量）、3D 倾斜与磁性吸附；光色默认取明暗主题的主色 RGB 值，`glowColor`（RGB 三元组字符串）可覆盖。
- 移动端（<768px）与 `prefers-reduced-motion` 下自动禁用动画，仅保留静态卡片。

### 徽章 / 提示条 / 弹窗 / Toast

- `.badge-*`：`rounded-full` 的语义状态徽章（success/warning/danger/muted/primary）。
- `.notice-*`：页面内持久提示条，与 Toast 同一视觉语言，带状态图标。
- `.modal-*`：`modal-backdrop`（遮罩 + `backdrop-blur-sm`）+ `modal-panel`（`rounded-2xl`、状态色顶部条）。
- `.toast-*`：`toast-viewport` 顶部居中（`z-[80]`，高于 Modal 遮罩 `z-[70]`），带进度条与进入/离开动画。

### 环境呼吸层（`.FloatingBackground`）

- 位置：`frontend/src/components/FloatingBackground/` + `frontend/src/hooks/useFloatingBackground.ts`，纯 Canvas 循环飘动背景，无第三方依赖。
- 三种几何形状（Z 形 / 正方形 / 平行四边形）做「水平匀速漂移 + 垂直正弦摆动」，形状透明度 0.04~0.15、单程穿越约 60~120s、无限循环。

#### Props

| Props | 默认 | 说明 |
| --- | --- | --- |
| `theme` | `"dark"` | `dark` / `light` / `auto`；`auto` 跟随 `html.dark` 类（MutationObserver），400ms 逐通道过渡 |
| `transparent` | `false` | `true` 时不绘制背景色，只清屏，站点令牌背景透出 |
| `opacity` | `1` | 全局透明度倍率 |
| `speed` | `1` | 全局速度倍率 |
| `shapeCount` | `7` | 形状数量，夹取 3~40 |
| `calm` | `false` | 焦点减速 ×0.5（平滑过渡） |
| `scrollWind` | `false` | 滚动风速：静止 0.5x、快速滚动最高 1.5x |
| `adaptive` | `true` | <768px 时 ≤6 个、速度 ×2/3、透明度 ×0.5 |

#### 站点接入标准

| 页面 | 配置 | 备注 |
| --- | --- | --- |
| 认证页（`AuthShell`） | `theme="auto" transparent shapeCount={10}` + 卡片聚焦 `calm` | 默认数量，`ambientShapeCount` 可覆盖 |
| 授权确认 | `ambientShapeCount={4}` | 信任时刻氛围减半 |
| 用户中心 | `theme="auto" transparent scrollWind shapeCount={10}` | 滚动风速联动 |
| 管理后台 | `theme="auto" transparent shapeCount={4} opacity={0.5}` | 极致克制 |

#### 层叠与约束

- 画布类为 `pointer-events-none absolute inset-0 z-0 block h-full w-full`；父容器需 `relative`，前景内容相对定位并位于画布之后。
- 画布必须垫底（z-0），内容永远在上；页脚等静态兄弟元素需 `relative` 才能压住画布。
- `prefers-reduced-motion` 时只绘制静态单帧；后台标签切回 dt 夹取 100ms；卸载清理 rAF/监听/Observer/定时器。
- 完整设计说明见 [`../../docs/superpowers/specs/2026-08-14-ambient-background-design.md`](../../docs/superpowers/specs/2026-08-14-ambient-background-design.md)。

---

## 页面模式

- **认证/引导页（登录、注册、邀请注册、找回/重置密码、邮箱验证、授权确认）：** `AuthShell`
  —— 居中单卡片（`max-w-md`）、极光背景（`AuroraBackground`）、顶部品牌 + 标语、底部备案信息。
- **已登录页（用户中心、管理后台）：** `AppHeader`（品牌 + 主题切换 + 操作按钮）+ 内容区 + `SiteFooter`。
- **管理后台：** 顶部胶囊标签页切换（`PillTabs`）；「数据统计」概览为深色 Bento 网格（`MagicBento`）。
- **深色模式：** `useTheme` 读取 `localStorage("portal-theme")`，首帧渲染前在 `index.html` 内联脚本应用 `html.dark`。

---

## Anti-Patterns（Do NOT Use）

- ❌ 用 emoji 代替图标 —— 使用 SVG（项目内 `Brand`、`icons.svg`、Heroicons 风格图标）。
- ❌ 可点击元素缺少 `cursor-pointer`。
- ❌ 布局抖动型 hover（避免 scale 变换破坏布局；仅允许 1px 上移与阴影变化）。
- ❌ 低对比度文本 —— 正文保持 4.5:1 以上。
- ❌ 无过渡的即时状态变化 —— 使用 150–300ms 过渡/动画。
- ❌ 不可见的键盘焦点 —— 统一 `focus-visible` 2px 主色描边。

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide/内置 SVG)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
