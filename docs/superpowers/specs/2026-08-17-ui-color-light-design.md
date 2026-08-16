# UI 色彩与流动光效刷新设计

> 状态：设计稿 ｜ 日期：2026-08-17 ｜ 范围：`frontend/`（纯视觉刷新，无后端/API/数据库变更）

## 1. 目标

用户反馈当前界面「颜色太单调、无动效」。在不破坏「安全、可信、克制」品牌定位的前提下：

1. 扩充低饱和强调色板，用**信息分层的色彩层次**替代单一「安全蓝 + 石板灰」；
2. 增加**克制的流动光效**（按钮流光、渐变描边流动、极光层、标题流光规则线），让界面「活着」但不打扰操作。

主色安全蓝 `#0369A1` 保持不变——它是 SSO / 身份信任场景的首选（与本项目此前
ui-ux-pro-max 检索结论一致），所有信任关键动作（登录、授权、焦点环）继续使用主色。

## 2. 现状与约束

### 2.1 现状

- 色彩令牌集中在 `frontend/src/index.css` 的 `:root` / `.dark`，仅有
  primary/success/warning/destructive 四个彩色系，其余为中性灰；
- 页面级颜色几乎全部是 `bg-primary-soft text-primary`（用户中心各分区图标、应用图标占位），
  后台「数据统计」的 Bento 卡片共用同一青色 `--bento-label: #38bdf8`；
- 图表默认系列色仅 primary/success/warning；
- 动效已有：认证页极光背景（AuroraBackground）、全站 Canvas 漂浮背景（FloatingBackground）、
  按钮按压/悬浮、ShinyText、卡片签名渐变描边（静态）等；**已登录页**（用户中心/管理后台）
  除极淡 Canvas 背景与 Bento 光标辉光外基本静态，视觉最「单调」。

### 2.2 约束

- 品牌五大原则（[BRAND.md](../../../design-system/lipass/BRAND.md)）：信任优先、克制的科技感、
  以动衬静、单一事实来源、无障碍与节能；
- 禁用：霓虹/大面积 AI 紫粉渐变、纯黑、玻璃拟态大背景；语义色只表达状态；
- WCAG AA：正文对比 ≥ 4.5:1，UI 组件/图形 ≥ 3:1；焦点始终可见；
- `prefers-reduced-motion: reduce` 时全部动效单帧（`index.css` 全局规则已内置）；
- 动效只动 `transform/opacity/background-position`，不触发布局抖动；
- 生产 CSP `style-src 'self'`：沿用现有 `style={{...}}` 属性的既有模式，不新增内联脚本/远程资源；
- 颜色、动效令牌只存在于 `index.css`，组件内禁止新增硬编码 hex。

## 3. 方案与取舍

### 3.1 色彩：六色低饱和强调色板

主色仍为安全蓝。新增 6 个强调色相（与现有极光层的青/靛/紫同族，避免引入陌生色系）：

| 色相 | 浅色 strong | 浅色 soft | 深色 strong | 深色 soft（rgba 底） |
| --- | --- | --- | --- | --- |
| cyan | `#0E7490` | `#CFFAFE` | `#67E8F9` | `rgba(103,232,249,.14)` |
| teal | `#0F766E` | `#CCFBF1` | `#5EEAD4` | `rgba(94,234,212,.14)` |
| indigo | `#4338CA` | `#E0E7FF` | `#A5B4FC` | `rgba(165,180,252,.16)` |
| violet | `#6D28D9` | `#EDE9FE` | `#C4B5FD` | `rgba(196,181,253,.16)` |
| amber | `#B45309` | `#FEF3C7` | `#FCD34D` | `rgba(252,211,77,.14)` |
| rose | `#BE123C` | `#FFE4E6` | `#FDA4AF` | `rgba(253,164,175,.14)` |

- strong 均取 700 级，配 soft 底色时文本对比 ≥ 4.5:1；深色 strong 取 300/400 级，
  在深色表面上的对比同样满足 AA；
- 每色相生成 Tailwind 令牌：`--color-accent-{hue}` 与 `--color-accent-{hue}-soft`，
  组件用 `text-accent-teal` / `bg-accent-indigo-soft` 等语义类引用；
- **amber/rose 只做装饰性使用**（图标瓦片、图表系列、分区规则线、Bento 标签），
  状态提示永远走 warning/destructive，避免语义混淆；
- 强调色总面积占比控制在 ≤15%，正文保持 foreground/muted；主色仍占彩色面积的大头。

应用 ID → 色相的分配用稳定字符串哈希（`frontend/src/lib/accent.ts` 的 `accentFor(id)`），
保证同一应用/实体每次渲染颜色一致，刷新页面不跳色。

### 3.2 流动光效

| 位置 | 效果 | 实现 | 周期 |
| --- | --- | --- | --- |
| `.btn-primary` | 左→右斜向扫光 + 停顿 | `::after` 渐变 `translateX(-130%→130%)` | 4.8s 循环 |
| `.card-signature`（认证卡） | 蓝→青→紫→青蓝描边沿 140° 缓慢流动 | 双层背景的 `background-position` 动画 | 14s |
| `AppHeader` 底部 | 1px 全长流光渐变线 | `.flow-rule`（brand 渐变 + 背景位移） | 8s |
| 用户中心 / 管理后台 | 极光层（复用 aurora-blob，透明度再降） | 新增 `.aurora-soft` 包装 | 16/20/24s |
| 分区标题下方 | 短流光规则线 | `.flow-rule`（`w-14 h-[3px]`） | 8s |
| `PillTabs` 活动标签 | 扫光 | 复用 `btn-sheen` 关键帧 | 4.8s |
| Bento 统计卡 | 标签/图标/辉光/迷你图按卡片色相着色 | 卡片级 `--bento-label` / `--glow-color` | 跟随现有光标辉光 |
| 图表 | 默认系列色扩展为多色相；认证方式分布条按方式着色 | `LineChart.DEFAULT_COLORS` + 分布条 map | — |

- 认证页本身已有 AuroraBackground + FloatingBackground + StrokeText 描字动画，**不再加码**，
  只在卡片描边上增加缓慢流动；
- 全部效果 `pointer-events: none`，仅合成层动画；`prefers-reduced-motion` 由全局规则降为单帧；
- 后台 Bento 已有关标聚光/粒子星点，本次只做「按色相着色」，不新增后台动效浓度。

### 3.3 取舍

- 不做布局重构、不动信息架构——这是**视觉刷新**，降低回归面；
- 不用玻璃拟态、霓虹、大面积渐变背景（品牌禁用清单）；
- 不改认证页氛围浓度（信任场景优先可读性）。

## 4. 接口与数据模型

无任何 API / 数据库 / OIDC 契约变更。`AppOut.client_id` 仅用于前端本地生成占位瓦片颜色，
不上送、不落库。

## 5. 安全影响

- 不引入第三方脚本、字体、图片或远程资源；
- 不修改 CSP、Cookie、会话、认证流程；
- 动效尊重 `prefers-reduced-motion`，移动端沿用 `FloatingBackground` 的自适应降级；
- 无用户数据泄露面变化。

## 6. UI 设计落地

令牌与动效以 [MASTER.md](../../../design-system/lipass/MASTER.md) 更新后的快照为准，
代码事实在 `frontend/src/index.css`。落地页面：

| 页面/组件 | 改动 |
| --- | --- |
| `index.css` | 6 色强调令牌（明/暗）、`--color-secondary`、`.flow-rule`、`.aurora-soft`、`btn-sheen`、签名卡流动 |
| `lib/accent.ts` | 色相枚举 + `accentFor(id)` 哈希 + 类名映射 |
| `DashboardPage` | 应用/头像占位瓦片按 ID 着色；分区图标按色相分层；分区标题流光规则线；极光层 |
| `AdminStatsPanel` | 6 张概览卡各配色相；迷你图/进度条跟随卡色；认证方式条按方式着色；趋势图多色 |
| `MagicBento` | item 支持 `accent`（rgb 三元组 + hex），卡片级覆盖辉光/标签/图标色 |
| `LineChart` | 默认系列色升级为 6 色相循环 |
| `AdminPage` / `AppHeader` / `PillTabs` | 极光层（更低浓度）/ 顶部流光线 / 活动标签扫光 |

## 7. 验收标准

- [ ] `accentFor` 确定性：同输入同色相、不同输入分布到多个色相；有单元测试；
- [ ] `MagicBento` 支持 item 级 `accent` 且不破坏现有 props；有单元测试；
- [ ] `cd frontend && npx tsc -b && npm run lint && npm test && npm run build` 全绿；
- [ ] 视觉截图检查：登录页（浅/深色）、用户中心、管理后台统计——色彩层次与流动光效可见；
- [ ] 抽查强调色文本在 soft 底上的对比 ≥ 4.5:1；
- [ ] `prefers-reduced-motion` 下新增动效均为单帧（全局规则覆盖）；
- [ ] 无新增硬编码 hex 进入 `pages/`、`components/`（令牌内除外）。

## 8. 风险

- **动效性能**：全部走合成层或背景位移，尺寸小；移动端极光层与 Canvas 均有降级，风险低；
- **色彩与语义混淆**：amber/rose 限制在装饰场景，状态语义色不替换；
- **观感主观性**：若用户希望更浓烈，可通过调高 `.aurora-soft` 透明度与强调色占比单点迭代，
  不需要重做结构。

## 9. V2.0 增补（海玻璃 Sea Glass + 科技氛围层）

**用户迭代指令汇总**：① 主界面也要科技感光效；② 允许跳出既有设计约束，做独特配色；
③ 全部使用淡色系、不要重色；④ 不要粉色系；⑤ 从七套候选色卡中选定「H · 海玻璃」。

最终落地：

- **配色**：全淡色系海玻璃主题——底色 `#F6FBF9`（深色 `#172321` 深水绿夜色，不压黑）、
  主色浅水绿 `#2F7F74`（深色 `#7FD4C6`）、次级冰蓝 `#4A8FBF`；六个雾面强调色相
  `ice/aqua/lilac/sage/mint/sand`（稳定哈希分配），全部低饱和、无粉色、无重色；
  按钮/签名描边/流光线统一用粉彩渐变 `#C9F3E7→#BDE9EC→#C9DFF7→#E4F5E3`，
  按钮文字用深青 `#24433E` 保持 WCAG AA。
- **主界面科技光效**：新增 `TechAmbience` 组件——缓移网格（56px 基线 + 336px 亮线，
  径向渐隐遮罩，26s 无缝循环）、两条错峰扫掠光束（10s）、六枚呼吸光点（5.5s）。
  认证页默认浓度接入，用户中心 `soft` 淡版，管理后台保持克制不接入；品牌 Logo 加海玻璃辉光。
  移动端隐藏光束/光点并停用网格动画；`prefers-reduced-motion` 全局单帧。
- **治理**：色相令牌更名对齐真实颜色（cyan/teal/… → ice/aqua/lilac/sage/mint/sand），
  `MASTER.md` 与 `BRAND.md`（V2.0）同步更新；CHANGELOG 记录两次视觉迭代。

## 10. V2.1 增补（D1 雾灰深色 + 半透明按钮）

用户反馈：深色页面仍太重、按钮色块违和。修订如下：

- **深色模式**切换为「D1 雾灰」柔和中间调：背景 `#3A3F45`、表面 `#434950`（平均亮度约为
  旧深水绿的 3 倍），前景 `#F0F2F4`、弱化 `#B8C0C7`；语义色与六强调色同步改为雾面低饱和变体；
  Bento 深色卡、`theme-color`、preflight 兜底背景与 FloatingBackground 调色板一并对齐。
- **主按钮**从多色粉彩渐变改为半透明单色着色：浅色 `rgba(47,127,116,.10)`、深色
  `rgba(127,212,198,.13)`，加 1px 同色系细描边；文字浅色 `#24433E`、深色 `#D7EFEA`。
  hover 只加深底色并抬升阴影，不再平移渐变。签名描边与流光线的深色透明度同步下调 15–20%。
- 保留：科技氛围层、扫光、强调色稳定哈希分配与全部无障碍/动效降级约束。

## 11. V2.2 增补（光效强化 + 后台接入）

用户反馈：光效不够明显、后台也要。修订如下：

- `TechAmbience` 从 2 光束/6 光点升级为 3 光束（8s，错峰 1s/3.6s/6.4s）/8 光点；网格亮线透明度
  提升约 40%，浅色光束透明度 0.18→0.26、深色 0.14→0.20；光点 6px→7px 并加大辉光半径。
- 认证卡新增 `.card-halo` 呼吸辉光（6s，浅水绿径向光晕，`isolation: isolate` 保证垫底）；
  `AuroraBackground` 新增第四枚暖沙光斑（`aurora-drift-4`），前三枚透明度整体提升 20~25%。
- 管理后台接入 `aurora-soft` + `TechAmbience soft`；表格/卡片仍为不透明 `bg-surface`，
  光束只在内容间隙与页边可见，可读性不受影响；移动端仍隐藏光束/光点。
- 性能边界不变：仅 `transform/opacity/background-position`，`prefers-reduced-motion` 单帧。

## 12. V2.3 增补（修复关键帧缺失并提速）

- **缺陷**：`tech-grid-pan`/`tech-beam-sweep`/`tech-dot-pulse` 三个关键帧只有 `animation` 引用、从未定义，
  网格/光束/光点完全静止（光束基态 `opacity:0` 且动画不生效，故不可见）——这正是「光效不动」的根因。
- **修复与提速**：补齐三组关键帧；网格 26s→12s，光束 8s→6s 且三条错峰更频繁（0.5s/2.5s/4.5s），
  光点 5.5s→3.6s 并加 7px 上下浮动；极光 16~24s→11~16s、振幅加大，签名描边 14s→9s，
  按钮扫光 5s→4s，卡片辉光 6s→4.5s（含轻微缩放）。动画约束与降级策略不变。

## 13. V2.4 增补（主文字改用 BlurText）

- 主界面展示主文字（认证页标题、用户中心问候语）由 StrokeText 描边动画替换为 React Bits
  `BlurText`（`motion/react`）：按词从上方模糊浮现、错峰 100–120ms，进入视口触发。
- 新增依赖 `motion`（生产按需分包，audit 0 漏洞）；保留 `as` 语义标签与
  `prefers-reduced-motion` 静态降级；StrokeText 组件保留未删，后续如需描边标题可复用。

## 14. V2.5 增补（极光节奏放慢）

- 用户反馈极光太快：四枚光斑周期由 11/13/16/14s 调整为 18/22/28/24s（振幅不变），
  回归舒缓的呼吸感；扫掠光束（6s 三组错峰）与光点（3.6s）节奏保持不变。
