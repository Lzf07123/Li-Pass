# 循环飘动氛围层（环境呼吸感）设计

- 日期：2026-08-14
- 状态：已实施完成（2026-08-14）
- 范围：前端品牌氛围动效（`frontend/src`）
- 技术栈：React 19 + TypeScript + 原生 Canvas 2D，无第三方依赖
- 关联文档：[品牌 UI 设计报告](../../../design-system/portal-oss/BRAND.md)（品牌意图，第 4 章）、[设计系统快照](../../../design-system/portal-oss/MASTER.md)（落地规格）

## 1. 目标

把品牌氛围从「一次性入场效果」升级为「恒定环境呼吸感」：极慢、极淡、永不停止、永不阻塞。三种几何形状（Z 形 / 正方形 / 平行四边形）在画布中做「水平匀速漂移 + 垂直正弦摆动」的复合运动，成为所有页面的统一背景暗线。

非目标：不做 DOM/CSS 元素版本（Canvas 为唯一实现）；盘旋公转、锁钥组合等其余轨迹暂缓；不改后端与接口。

## 2. 设计原则

- **永不退场**：所有形状 `infinite` 循环，越出边缘后从另一侧回绕。
- **用户无感**：形状自身透明度 0.04~0.15，单程穿越屏幕约 60~120s。
- **永不阻塞**：画布 `pointer-events: none`、`aria-hidden`，只做 Canvas 位图绘制（不触碰 DOM 布局）。
- **性能友好**：`devicePixelRatio` 封顶 2；过淡形状跳过绘制；每帧清屏重绘，无节点堆积。
- **帧率无关**：速度参数保持「px/帧、rad/帧」的直观语义，但按 `dt` 归一化到 60fps 基准，120Hz 高刷屏不快进、掉帧不变慢。
- **无障碍**：`prefers-reduced-motion` 时只渲染静态单帧；移动端自动减量省电。

## 3. 模块设计

### 3.1 核心逻辑（`frontend/src/hooks/useFloatingBackground.ts`）

统一入口：

```ts
useFloatingBackground(canvasRef, {
  theme,        // "dark" | "light" | "auto"，默认 "dark"
  opacity,      // 全局透明度倍率，默认 1
  speed,        // 全局速度倍率，默认 1
  shapeCount,   // 形状数量，默认 7（夹取 3~40）
  transparent,  // 透明画布（不绘制背景色），默认 false
  calm,         // 焦点减速：×0.5，默认 false
  scrollWind,   // 滚动风速：静止 0.5x ~ 快速滚动 1.5x，默认 false
  adaptive,     // 移动端自动减量，默认 true
});
```

关键机制：

- **形状分层**：按索引分三层「近大远小」——远景（80~120px、透明度 0.04~0.07、速度 0.15~0.2px/帧）、中景（45~80px）、近景（30~45px、透明度 0.11~0.15、速度 0.28~0.35px/帧）。
- **坐标与回绕**：横坐标为归一化值（0~1），绘制时乘画布宽度；越界后按「半宽缓冲」回绕，实现无缝穿行。纵坐标叠加 `sin(相位) × 振幅(20~50px)`。
- **错峰**：每个形状随机初始相位与速度，方向左右混合，避免整齐划一。
- **平滑系数**：`calm`、`scrollWind`、主题颜色都逐帧指数逼近目标，避免速度/颜色突变。
- **生命周期**：窗口 resize 防抖 200ms 重建画布；卸载时取消 rAF、解绑监听、断开 MutationObserver、清理防抖定时器；`requestAnimationFrame` 不可用时回退为静态单帧。

### 3.2 组件入口（`frontend/src/components/FloatingBackground/index.tsx`）

- 渲染单个 `<canvas>`：`pointer-events-none absolute inset-0 z-0 block h-full w-full`。
- 父容器必须是定位元素（如 `relative`）；前景内容需相对定位且位于画布之后（`relative`/`z-10`），不透明卡片天然遮蔽其下形状。
- 导出 `FloatingBackgroundProps` 类型；Next.js（App Router）使用时在文件首行加 `'use client'`。

## 4. 主题与交互联动

- **主题同步（`theme="auto"`）**：以 `<html>` 的 `dark` 类为唯一事实源，用 MutationObserver 跟随变化，避免多个组件各自持有 `useTheme` 状态导致失步；颜色逐通道 400ms 平滑过渡，静态帧模式下直接快照目标调色板。浅色主题描边自动改用深灰（`rgb(105,112,125)`），银灰在浅底上不可见。
- **焦点减速（`calm`）**：认证页卡片容器监听 `focusin/focusout`，焦点仍在容器内（`relatedTarget` 判断）则保持减速，速度平滑降为 0.5 倍。
- **滚动风速（`scrollWind`）**：用户中心监听滚动，滚动幅度映射为风速并逐帧指数衰减——静止回落 0.5x 慢呼吸，快速滚动最高 1.5x，永不停止。**修正说明**：原方案公式在静止时会把速度算成 0 导致动画冻结，本实现改为「静止 0.5x、滚动加速」，保留 0.5x~1.5x 区间。
- **移动端减量（`adaptive`）**：`max-width: 767px` 时形状数 ≤6、速度 ×2/3、透明度 ×0.5。

## 5. 分页接入标准（后续统一风格以本表为准）

| 页面 | 外壳 | 接入配置 | 说明 |
| --- | --- | --- | --- |
| 认证页（登录/注册/邀请/找回/重置/验证） | `AuthShell` | `theme="auto" transparent shapeCount={10}` + 卡片聚焦 `calm` | 迎宾氛围，最丰富 |
| 授权确认 | `AuthShell` | 追加 `ambientShapeCount={4}` | 信任时刻，氛围减半 |
| 用户中心 | `DashboardPage` | `theme="auto" transparent scrollWind shapeCount={10}` | 活跃但不打扰 |
| 管理后台 | `AdminPage` | `theme="auto" transparent shapeCount={4} opacity={0.5}` | 极致克制，仅作呼吸点缀 |

新增页面规则：一律 `transparent + theme="auto"`；形状数量按页面信任权重取 4~10；后台/表格类页面 `opacity ≤ 0.5`；表格、表单等核心交互区域必须由不透明表面或禁飘区保证可读性。

## 6. 可访问性与性能

- `prefers-reduced-motion`：不启动 rAF，仅绘制静态单帧；偏好变化时动态启停。
- 后台标签切回：`dt` 夹取 100ms，防止形状瞬移跳变。
- 移动端减量见第 4 节；动画只读 Canvas，不产生 DOM 节点与回流。
- 包体积零新增：全部为项目内代码，无第三方依赖。

## 7. 验证

- `npm run test`：22 个测试文件共 55 用例通过，其中 `FloatingBackground.test.tsx` 8 个用例覆盖：形状绘制与循环推进、透明画布、`theme="auto"` 跟随 `html.dark`、`calm` 减速减半、`scrollWind` 滚动提速、移动端限量、减弱动效静态帧、卸载清理。
- `npm run lint`（oxlint）与 `npm run build`（tsc + vite）通过。
- 待补：浏览器可用的截图对比（`design-system/portal-oss/preview/` 现有预览图为 2026-08-12 旧版，需在氛围层落地后重新生成）。

## 8. 后续统一风格约束

- ✅ 所有页面背景氛围必须复用 `FloatingBackground`，配置走第 5 节标准，不在页面内自写 Canvas / CSS 循环动画。
- ✅ 视觉参数只允许出现在 `index.css` 令牌与组件 Props 中；组件内禁止硬编码 hex 与文案。
- ✅ 新页面复用 `AuthShell` / `AppHeader` / `card` / `btn` 既有模式，先查 MASTER.md 再写代码。
- ❌ 禁止把氛围层放到内容之上（z-index 冲突）、忽略 `prefers-reduced-motion`、在表格区引入形状遮挡。
