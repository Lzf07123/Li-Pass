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
**Updated:** 2026-08-17（与 `frontend/src/index.css`、`frontend/src/components/` 对齐；
全站切换为「海玻璃 Sea Glass」淡色系并新增科技氛围层，详见
`docs/superpowers/specs/2026-08-17-ui-color-light-design.md`）
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
| 背景 | `#F6FBF9` | `#3A3F45` | `bg-background` |
| 表面 | `#FFFFFF` | `#434950` | `bg-surface` |
| 表面 2 | `#EEF6F3` | `#4B5259` | `bg-surface-2` |
| 前景 | `#35423F` | `#F0F2F4` | `text-foreground` |
| 弱化文本 | `#71807A` | `#B8C0C7` | `text-muted` |
| 边框 | `#E1ECE8` | `#545C64` | `border-border` |
| 主色 | `#2F7F74` | `#7FD4C6` | `bg-primary / text-primary` |
| 主色悬停 | `#27685F` | `#A5E4D9` | `hover:bg-primary-hover` |
| 主色前景 | `#FFFFFF` | `#17332E` | `text-primary-foreground` |
| 次级色 | `#4A8FBF` | `#A8D4F0` | `text-secondary / bg-secondary-soft` |
| 成功 | `#2F8F5F` | `#86D6AC` | `text-success / bg-success-soft` |
| 警告 | `#A16207` | `#EAD48E` | `text-warning / bg-warning-soft` |
| 危险 | `#CF3D3D` | `#E8A49A` | `text-destructive / bg-destructive-soft` |
| 焦点环 | `#2F7F74` | `#7FD4C6` | `focus:ring-primary/20` |

**强调色板（信息分层，装饰性小面积使用）：**

| 色相 | 浅色 strong / soft | 深色 strong / soft | Tailwind 令牌 |
| --- | --- | --- | --- |
| ice | `#4A8FBF` / `#DFF1FA` | `#A8CBE8` / `rgba(168,203,232,.16)` | `text-accent-ice / bg-accent-ice-soft` |
| aqua | `#2F7F74` / `#D9F4EE` | `#7FD4C6` / `rgba(127,212,198,.16)` | `text-accent-aqua / bg-accent-aqua-soft` |
| lilac | `#7A6FC4` / `#EDEAFB` | `#B0A8DE` / `rgba(176,168,222,.18)` | `text-accent-lilac / bg-accent-lilac-soft` |
| sage | `#6E8F5E` / `#EAF2E3` | `#B0C79E` / `rgba(176,199,158,.18)` | `text-accent-sage / bg-accent-sage-soft` |
| mint | `#3F8F63` / `#E3F6E9` | `#9ADFAD` / `rgba(154,223,173,.16)` | `text-accent-mint / bg-accent-mint-soft` |
| sand | `#A9865B` / `#F7EFE0` | `#D9C49E` / `rgba(217,196,158,.16)` | `text-accent-sand / bg-accent-sand-soft` |

stable 哈希分配见 `frontend/src/lib/accent.ts` 的 `accentFor(id)`；Bento 深色卡标签色
（明暗主题共用，卡面恒为深色）另设 `--portal-bento-{ice,aqua,lilac,sage,mint,sand}[-rgb]` 令牌。

**色彩说明：** 海玻璃（Sea Glass）——磨砂浅水绿 + 冰蓝 + 蛋白石；全淡色系、**无粉色、无重色**。
前景/背景对比满足 WCAG AA（正文 ≥ 4.5:1）。强调色 strong 均取雾面 600 级（浅色）/300 级（深色），
配 soft 底时文本对比 ≥ 4.5:1；强调色只做装饰（瓦片/图例/规则线），状态语义色不被替代。
签名描边与流光线使用粉彩渐变（`--flow-gradient`）；主按钮改为半透明单色着色
（`--btn-primary-bg`，浅色 10% / 深色 13% 透明度）+ 细描边，文字用 `--brand-fg` 保证对比。
深色模式为「D1 雾灰」柔和中间调（不压黑），而非简单反色。

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
| `--shadow-sm` | `0 0.6px 1.8px rgba(24,58,51,0.04), 0 2.4px 7.2px rgba(24,58,51,0.05)` |
| `--shadow-md` | 在 `sm` 上叠加 `0 8px 24px rgba(24,58,51,0.08)` |
| `--shadow-lg` | 在 `md` 上叠加 `0 8px 32px rgba(24,58,51,0.1)` |
| `--ease-out` | `cubic-bezier(0.25, 0.1, 0.25, 1)`（入场） |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)`（按压/弹窗） |
| 时长 | `--motion-fast: 150ms`、`--motion-base: 250ms`、`--motion-slow: 350ms` |

交互统一：可点击元素必须有 `cursor-pointer`；hover 轻微上移（`translateY(-1px)`），按压 `scale(0.97)`；
`prefers-reduced-motion: reduce` 时所有动画缩短为 `0.01ms` 并保持单帧。

**流动光效（2026-08-17 新增，全部仅动 transform/opacity/background-position）：**

| 位置 | 效果 | 周期 |
| --- | --- | --- |
| `.btn-primary::after` | 斜向扫光 + 长停顿（`btn-sheen`），disabled 不发光 | 4s |
| `.card-signature` | 海玻璃粉彩描边沿 140° 流动（`signature-flow`） | 9s |
| `.flow-rule` | 浅水绿→冰蓝→淡丁香→鼠尾草渐变流动线（分区标题/顶栏） | 5s |
| `.aurora-soft` | 已登录页低浓度极光层（认证页保持默认浓度） | 18/22/28/24s |
| `.pill-tab.is-active::after` | 活动标签扫光（复用 `btn-sheen`） | 4s |
| `.tech-grid` | 缓移网格（56px 基线 + 336px 亮线，径向渐隐遮罩） | 12s |
| `.card-halo` | 认证卡后的浅水绿呼吸辉光（含轻微缩放） | 4.5s |
| `.tech-beam` | 周期性扫掠光束（三条错峰，斜切 16°） | 10s |
| `.tech-dot` | 呼吸光点（8 枚，错峰缩放/透明度脉动 + 7px 浮动） | 6s |

---

## Component Specs（对应 `frontend/src/components/` 与 `index.css`）

### 按钮（`.btn` 系列）

- `.btn-primary`：半透明单色着色（`--btn-primary-bg`，浅色 `rgba(47,127,116,.10)`、深色
  `rgba(127,212,198,.13)`）+ 1px 细描边 + `--brand-fg` 文字；hover 加深底色并抬升阴影，不做多色渐变色块。
- `.btn-primary::after`：斜向流光扫过按钮并长时间停顿，明暗主题各配不同亮度扫光；`disabled` 关闭。
- `.btn-secondary`：透明/表面背景 + 边框；hover 换 `surface-2`。
- `.btn-danger`：危险色背景 + 白色前景；hover 透明度降低。
- `.btn-ghost` / `.btn-link`：弱化/文字按钮，用于次要操作。
- 统一圆角 `rounded-lg`、`px-4 py-3`、`text-sm font-medium`，`disabled` 时 `opacity-50` 且不可点击。

### 卡片（`.card`）

- `bg-surface` + `border-border` + `rounded-2xl` + 弥散阴影。
- hover：`translateY(-1px)` 并切换 `--shadow-lg`；交互式卡片加 `.card-interactive`。
- `.card-signature`：认证页专用，叠加于 `.card` 之上，以海玻璃粉彩渐变替代描边（padding-box 表面 + border-box 渐变边框双背景）。
  描边层以 `background-position` 动画缓慢流动（14s）。

### 科技氛围层（`TechAmbience`）

- 位置：`frontend/src/components/bits/TechAmbience.tsx`，纯 CSS 装饰层，无第三方依赖。
- 结构：`.tech-grid`（缓移网格）+ 三条 `.tech-beam`（错峰扫掠光束）+ 八枚 `.tech-dot`（呼吸光点）。
- 接入：认证页 `AuthShell` 默认浓度；用户中心 `TechAmbience soft` 淡版；管理后台 `TechAmbience soft`
  淡版 + `aurora-soft` 极光层（V2.2 起按用户要求接入，表格区仍为不透明表面）。
- 认证页卡片叠加 `.card-halo`（浅水绿呼吸辉光）；`AuroraBackground` 含四枚光斑（水绿/薄荷/淡丁香/暖沙）。
- 约束：`aria-hidden`、`pointer-events: none`、移动端（<768px）隐藏光束与光点并停用网格动画；
  `prefers-reduced-motion` 下由全局规则降为单帧。

### 表单（`.label` / `.input` / `.input-sm`）

- 输入框：`bg-surface`、`rounded-lg`、`px-3 py-2.5`、`text-sm`。
- focus：主色边框 + `ring-2 ring-primary/20`；placeholder 用 `text-muted`。

### 胶囊标签（`PillTabs` / `.pill-tab`）

- 位置：`frontend/src/components/PillTabs.tsx` + `PillTabs.css`，管理后台顶部标签栏使用；基于 gsap，移植 React Bits PillNav 的圆环展开效果。
- 结构：`PillTabs` 内部渲染 `ScrollTabs`（`fadeColor="var(--portal-surface-2)"`），轨道为 surface-2 背景 + 9999px 圆角；每颗 `.pill-tab` 含 `.pill-tab-circle`（主色圆环）与 `.pill-tab-stack`（双层文案）。
- 交互：hover / 键盘聚焦时圆环从胶囊底部中心放大覆盖整颗胶囊，旧文案上滑、主色前景文案从下方滑入（进入 300ms / 离开 200ms）；活动标签固定为主色背景 + 主色前景，并有斜向扫光（`btn-sheen`）。`prefers-reduced-motion` 下瞬切。
- 保留 ScrollTabs 的横向滑动、边缘渐隐与深链居中能力。

### 主文字模糊浮现（`BlurText`）

- 位置：`frontend/src/components/bits/BlurText.tsx`，React Bits BlurText 的 TypeScript 移植版
  （JavaScript + CSS 变体，`motion/react` 驱动）。
- 用法：认证页标题（`AuthShell`）与用户中心问候语（`DashboardPage`）以 `as="span"` 包在 `h1` 内，
  `animateBy="words" direction="top"` 按词错峰模糊浮现；支持 `threshold/rootMargin` 视口触发、
  `animationFrom/animationTo/easing` 自定义与 `onAnimationComplete` 回调。
- 无障碍：`prefers-reduced-motion: reduce` 时静态渲染整段文本，跳过模糊位移动画。

### 数字滚动（`CountUp`）

- 位置：`frontend/src/components/bits/CountUp.tsx`，React Bits CountUp 的 TypeScript 移植版
  （`motion/react` 弹簧：`damping=20+40/duration`、`stiffness=100/duration`）。
- 用法：用户中心/会话监控/用户管理/应用管理/审计日志的「共 N 个…」计数，
  `from={0}`、`duration={0.8}`、`className="tabular-nums"`；支持 `separator` 千位分隔、
  `direction="up|down"`、`startWhen` 视口触发与 `onStart/onEnd` 回调。
- 无障碍：`prefers-reduced-motion` 或无 `requestAnimationFrame` 的环境直接显示目标值，不做墙钟动画。

### Bento 展示网格（`MagicBento` / `.magic-bento-card`）

- 位置：`frontend/src/components/bits/MagicBento.tsx` + `MagicBento.css`，后台「数据统计」概览卡片使用；基于 gsap，移植 React Bits MagicBento。
- 结构：`.magic-bento` 内为 `.card-grid.bento-section`，卡片为深色表面（浅色 `#0F172A` / 深色 `#111A2C`）；默认首卡跨两列，`emphasize` 项数值加粗放大（tabular-nums）；项支持 `icon`（标签前图标）、`footer`（底部扩展内容，如迷你趋势线/进度条）与 `href`（整卡渲染为路由链接）；`compact` 模式为等宽 3 列、单卡高 144px，适合嵌入页面顶部概览区。
- 交互：全局光标聚光（`.global-spotlight`）、悬停粒子星点、边框辉光（`--glow-*` 变量）、3D 倾斜与磁性吸附；光色默认取明暗主题的主色 RGB 值，`glowColor`（RGB 三元组字符串）可覆盖。
- 多色支持：item 可选 `accent: { rgb, hex }`，卡片级覆盖 `--glow-color`/`--bento-label`，
  标签底色/图标/辉光/页脚迷你图与进度条联动跟随（`color-mix`/`rgba(var(--glow-color))` 派生）。
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
- **管理后台：** 顶部胶囊标签页切换（`PillTabs`），8 个标签面板懒加载；「数据统计」概览为深色 Bento 网格（`MagicBento`）。
- **深色模式：** `useTheme` 读取 `localStorage("portal-theme")`，首帧渲染前在 `index.html` 内联脚本应用 `html.dark`。

---

## Anti-Patterns（Do NOT Use）

- ❌ 粉色系（粉红/品红/玫瑰）与大面积重色背景 —— 全站淡色系是硬性约束，强调色只用海玻璃六色。
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
