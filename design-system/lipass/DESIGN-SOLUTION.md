# Li&Pass 视觉设计全量方案 · Sea Glass（海玻璃）

> **版本**：V1.0 ｜ **日期**：2026-08-17 ｜ **状态**：已定稿并落地（2026-08-17 全量视觉刷新）
> **性质**：本文件是 Li&Pass 视觉设计的**完整设计方案汇总**，覆盖「色彩 + 组件 + 氛围光效 +
> 文字/计数动效 + 按钮状态 + 无障碍」全部决策；与 [BRAND.md](./BRAND.md)（品牌意图）、
> [MASTER.md](./MASTER.md)（实现速览）三份互补，代码事实始终以 `frontend/src/index.css` 为准。
> **模板化**：本方案已同步提炼进上层模板仓库 `Li&Design`（`REUSABLE-BRAND-SCHEME.md` +
> `reusable-tokens.template.css`），新项目按该模板填槽实例化。

## 1. 方案定位与决策时间线

目标一句话：在「安全可信」不丢失的前提下，把 Li&Pass 从单一「安全蓝 + 石板灰」升级为
**全淡色的海玻璃系统 + 可见的科技流动光效 + 优雅的文字/计数动效**。

决策时间线（与用户逐轮收敛，全部保留在 CHANGELOG 与 spec 增补中）：

1. 「颜色太单调」→ 引入六色强调色板与基础流动光效；
2. 「主界面也要光效、有科技感」→ 设计 TechAmbience（网格 + 光束 + 光点）；
3. 「跳出设计限制做独特配色」→ 提出深空极光方向；
4. 「全部淡色、不要重色」→ 回到全淡色系；
5. 「不要粉色系」→ 移除粉/品红，第六色相改 lime；
6. 七套色卡中选定 **H · 海玻璃**；
7. 「深色页面还是太重」→ 深色改为 **D1 雾灰** 柔和中间调；
8. 「按钮颜色太重、违和」→ 按钮改**半透明单色着色**；
9. 「强化光效、后台也加上」→ 光束/光点/网格提亮，后台接入淡版；
10. 「让光效动起来」→ 修复缺失的关键帧并整体提速；
11. 「极光太快」「光束光点也等比放慢」→ 极光 18/22/28/24s，光束 10s、光点 6s；
12. 主文字改用 React Bits **BlurText**、全部计数改用 **CountUp**；
13. 按钮状态审计：pending 只出现在被点击的按钮上。

## 2. 硬约束（不可破）

- **全淡色**：所有表面与装饰为浅色/雾面；**无粉色系、无大面积重色**。
- **WCAG AA**：正文 ≥ 4.5:1、图形/UI ≥ 3:1；所有强调色 strong-on-soft 组合已核算通过。
- **动效纪律**：只动 `transform/opacity/background-position`；每个 `animation` 必须有对应
  `@keyframes`；`prefers-reduced-motion` 降为单帧；移动端减量。
- **单一事实来源**：颜色/动效令牌只在 `index.css`；品牌文案只在 `brand.ts`；组件不硬编码 hex。
- **语义不混**：强调色只做装饰；成功/警告/危险永远走语义色。

## 3. 色彩系统

### 3.1 浅色（`:root`）

| 角色 | 值 | 令牌 |
| --- | --- | --- |
| 背景 | `#F6FBF9` | `--portal-bg` |
| 表面 / 表面 2 | `#FFFFFF` / `#EEF6F3` | `--portal-surface(-2)` |
| 前景 / 弱化 / 边框 | `#35423F` / `#71807A` / `#E1ECE8` | `--portal-fg/muted/border` |
| 主色 / hover / soft / fg | `#2F7F74` / `#27685F` / `#D9F4EE` / `#FFFFFF` | `--portal-primary*` |
| 次级 | `#4A8FBF`（soft `#DFF1FA`） | `--portal-secondary(-soft)` |
| 成功 / 警告 / 危险 | `#2F8F5F` / `#A16207` / `#CF3D3D` | `--portal-success/warning/destructive` |
| 焦点环 | `#2F7F74` | `--portal-ring` |
| 按钮着色 | bg `rgba(47,127,116,.10)`、hover `.17`、描边 `.26` | `--btn-primary-*` |
| 按钮文字 | `#24433E` | `--brand-fg` |

### 3.2 深色（`.dark`，D1 雾灰）

| 角色 | 值 |
| --- | --- |
| 背景 / 表面 / 表面 2 | `#3A3F45` / `#434950` / `#4B5259` |
| 前景 / 弱化 / 边框 | `#F0F2F4` / `#B8C0C7` / `#545C64` |
| 主色 / hover / soft / fg | `#7FD4C6` / `#A5E4D9` / `rgba(127,212,198,.16)` / `#17332E` |
| 次级 | `#A8D4F0`（soft `rgba(168,212,240,.16)`） |
| 成功 / 警告 / 危险 | `#86D6AC` / `#EAD48E` / `#E8A49A`（fg `#43211D`） |
| 按钮着色 | bg `rgba(127,212,198,.13)`、hover `.21`、描边 `.30` |
| 按钮文字 | `#D7EFEA` |

深色原则：**雾灰中间调，不压黑**（平均亮度约为旧深色的 3 倍）。

### 3.3 六强调色板（装饰专用）

| 色相 | 浅 strong / soft | 深 strong / soft | 典型用途 |
| --- | --- | --- | --- |
| ice | `#4A8FBF` / `#DFF1FA` | `#A8CBE8` / `rgba(168,203,232,.16)` | 会话/设备、密码方式条 |
| aqua | `#2F7F74` / `#D9F4EE` | `#7FD4C6` / `rgba(127,212,198,.16)` | 邮箱验证、可信设备 |
| lilac | `#7A6FC4` / `#EDEAFB` | `#B0A8DE` / `rgba(176,168,222,.18)` | 邮箱变更、TOTP |
| sage | `#6E8F5E` / `#EAF2E3` | `#B0C79E` / `rgba(176,199,158,.18)` | 安全设置、图表 |
| mint | `#3F8F63` / `#E3F6E9` | `#9ADFAD` / `rgba(154,223,173,.16)` | 应用广场、注册增长 |
| sand | `#A9865B` / `#F7EFE0` | `#D9C49E` / `rgba(217,196,158,.16)` | 密码分区、恢复码 |

实体 → 色相用稳定哈希（`lib/accent.ts` 的 `accentFor(id)`），刷新不跳色。Bento 深色卡标签
共用一组亮色令牌 `--portal-bento-{ice,aqua,lilac,sage,mint,sand}[-rgb]`。

### 3.4 渐变与装饰令牌

- `--flow-gradient`：浅水绿→冰蓝→淡丁香→鼠尾草（流光规则线/顶栏流光线；深色用半透明变体）。
- 签名卡描边：海玻璃粉彩五段 `rgba` 渐变，沿 140° 缓慢流动。
- 阴影：水绿 tint（`rgba(24,58,51,…)`），三档透明度总和 < 0.1。
- 科技层：`--tech-grid-line/-accent/-accent-2`、`--tech-beam(-2/-3)`、`--tech-dot-glow`（明暗两套）。

## 4. 组件样式规格

- **`.btn-primary`**：半透明单色着色 + 1px 同色细描边 + `--brand-fg` 文字；hover 加深底色并抬升阴影；
  `::after` 斜向扫光（`btn-sheen` 4s）；`disabled` 关闭扫光。不再使用多色渐变色块。
- **`.card` / `.card-signature` / `.card-halo`**：认证卡 = 表面双背景 + 粉彩流动描边（9s）+
  卡后浅水绿呼吸辉光（4.5s，含轻微缩放）；`.brand-halo` 给认证页 Logo 辉光。
- **`.badge-*` / `.notice-*` / `.modal-*` / `.toast-*`**：语义色 + soft 底；Toast `z-80` 高于 Modal `z-70`。
- **`PillTabs`**：活动标签实色主色 + 扫光（4s）；轨道 surface-2 胶囊。
- **`MagicBento`**：深色卡（浅 `#1A2B27` / 深 `#363D44`）；`title` 支持 ReactNode（嵌入 CountUp）；
  卡片级 `accent:{rgb,hex}` 驱动标签/图标/辉光/迷你图同色。
- **`BlurText`**：见 §6；**`CountUp`**：见 §6；**`TechAmbience`**：见 §5。

## 5. 氛围与流动光效

| 层 | 实现 | 节奏 | 页面浓度 |
| --- | --- | --- | --- |
| FloatingBackground | Canvas 几何漂移（无第三方依赖） | 60–120s 单程 | 认证 10 / 授权 4 / 中心 10 / 后台 4×0.5 |
| AuroraBackground | 4 枚弥散光斑（水绿/薄荷/淡丁香/暖沙） | 18/22/28/24s | 认证默认；中心/后台 `aurora-soft` |
| TechAmbience | 缓移网格（56px+336px 亮线，径向渐隐遮罩）+ 3 条扫掠光束 + 8 枚呼吸光点 | 网格 12s、光束 10s（错峰 0.8/4.2/7.5s）、光点 6s | 认证默认；中心/后台 `soft` |
| card-halo | 认证卡呼吸辉光 | 4.5s | 认证页 |
| signature / flow-rule / btn-sheen | 描边流动 / 流光规则线 / 按钮扫光 | 9s / 5s / 4s | 全站 |

**关键教训**：`tech-grid-pan` / `tech-beam-sweep` / `tech-dot-pulse` 曾只有 `animation` 引用、
未定义 `@keyframes`，导致网格/光束/光点完全静止、光束不可见——**每个动画必须核对关键帧存在**。
移动端（<768px）隐藏光束/光点并停用网格动画；所有循环 `prefers-reduced-motion` 单帧。

## 6. 文字与计数动效

- **BlurText**（`motion/react`）：认证页标题与用户中心问候语按词从上方模糊浮现（delay 100–120ms、
  stepDuration 0.35s、`justify-center`）；`prefers-reduced-motion` 下静态渲染整段文本。
- **CountUp**（`motion/react` 弹簧）：全部计数展示（用户中心、各管理面板「共 N…」、统计概览六卡、
  认证方式分布、地域徽章、会话确认弹窗、应用「已登录 · N 台设备」）；`from=0`、`duration=0.8–1s`、
  千位分隔；无 rAF / reduced-motion 直接落定目标值。坐标轴、时间、百分比、字节保持静态文本。

## 7. 按钮状态规范（全量审计结论）

- **pending 只属于被点击的按钮**：成对/并列按钮各自持有独立 action 或按目标区分状态；
  其它按钮仅 `disabled` 防并发、不显示状态。
- 触发按钮与确认弹窗分离：运行状态只显示在弹窗确认按钮上。
- 已修复并回归覆盖：授权确认（同意/拒绝）、登出确认（SSO/本网站）、批量启用/禁用、
  列表行停用/启用、黑名单封禁/解封、会话「全部下线」。

## 8. 无障碍与性能

- 对比度核算：六强调色 strong-on-soft ≥ 4.5:1（浅）与深色软底组合均通过；按钮文字
  `#24433E`/`#D7EFEA` 与半透明底对比 ≥ 4.5:1。
- `prefers-reduced-motion`：CSS 动画全局单帧；BlurText/CountUp 跳过动画。
- 性能：动画仅合成层属性；无大尺寸 blur 滤镜；移动端减量；Canvas 有自适应与焦点减速。

## 9. 验收清单

- [ ] tsc / lint / vitest / build 全绿（当前 161 用例）
- [ ] 生产 CSS 含全部令牌与关键帧（`accent-*`、`tech-*`、`btn-sheen` 等）
- [ ] 无粉色系、无大面积重色；深浅两套令牌齐全
- [ ] 强调色文本对比 ≥ 4.5:1
- [ ] 每个 `animation` 都有对应 `@keyframes`
- [ ] pending 状态只出现在被点击的按钮上
- [ ] 375/768/1024/1440 响应式无横向滚动
- [ ] `prefers-reduced-motion` 下单帧、BlurText/CountUp 直接落定

## 10. 与 Li&Design 模板的映射

本方案即模板仓库「海玻璃示例」的来源：槽位 7–12、16、19、21–22 已按本表填为 Li&Pass 现值；
令牌骨架 `reusable-tokens.template.css` 已同步强调色板、半透明按钮与科技光效令牌；
新项目复制模板、替换 `{{PROJECT_PREFIX}}`、按槽位填色即可实例化。
