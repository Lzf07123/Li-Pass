# 视觉设计对齐 Li&Design V1.4 子模块设计

> 状态：设计稿 ｜ 日期：2026-08-20 ｜ 范围：`frontend/` + `design-system/lipass/`（纯视觉/文档，无后端/API/数据库变更）

## 1. 目标

Li&Design 子模块已指向 V1.4（25b49c0）。按模板仓库的「存量项目对齐」路径（REUSABLE-BRAND-SCHEME §7 历史差异处理）与 V1.4 验收清单，把 Li&Pass 的落地视觉对齐到子模块基准：

1. 浅色语义色改用 V1.3 AA 调校值（muted `#64736C` / success `#2A7C52` / warning `#9A5C05` / destructive `#C43737`），消除旧值对比度不达 4.5 的历史差异；
2. 深色带文字软底组件引入 `*-soft-solid` + `*-soft-fg` 令牌（实色粉彩底 + 深字），不再依赖「语义色作底 + 深青字」的隐式映射；
3. 原生 select / 复选 / 单选 / 文件按钮 / 表格空状态等 V1.4 控件按模板类落地，组件不再各自拼 Tailwind 工具类。

## 2. 现状与约束

### 2.1 现状差距（对照 `PROJECTS-IMPLEMENTATION-INDEX.md` §2.2/§3 与项目 `index.css`）

| 项 | 当前实现 | V1.4 基准 |
| --- | --- | --- |
| 浅色 muted | `#71807A`（3.96 ❌） | `#64736C`（4.77 ✅） |
| 浅色 success | `#2F8F5F`（3.85 ❌） | `#2A7C52`（4.89 ✅） |
| 浅色 warning | `#A16207`（4.71） | `#9A5C05`（5.14 ✅） |
| 浅色 destructive | `#CF3D3D`（4.58） | `#C43737`（5.09 ✅） |
| 深色软底令牌 | 无 `*-soft-solid` / `*-soft-fg` | `.dark` 内 4 组实色粉彩令牌 |
| 深色徽章 | `.dark .badge-*` 用 `bg-* + text-primary-foreground` | `background-color: var(--portal-*-soft-solid)` + `color: var(--portal-*-soft-fg)` |
| 原生 select | `<select className="input-sm">`（无 chevron） | `.select` / `.select-sm`（双三角渐变 chevron、option 走令牌） |
| 复选/单选 | 组件内 `h-4 w-4 accent-primary` 或裸控件 | 全局 18px + `accent-color` 主色 + `cursor: pointer` |
| 文件按钮 | `file:` Tailwind 工具类堆叠、无 hover | `input[type="file"]::file-selector-button` 全局类（surface-2 → primary-soft hover） |
| 表格空状态 | `AdminUsersPanel` 空行 `py-10 text-center text-sm text-muted` | `.table-empty-row`（居中 muted，容器虚线） |

### 2.2 约束

- 品牌五大原则与全淡色口径不变（[BRAND.md](../../../design-system/lipass/BRAND.md)）；
- 颜色/动效令牌只在 `frontend/src/index.css`；组件不硬编码 hex；
- 只移植项目实际用到的 V1.4 控件；自定义下拉、下拉菜单、建议选项、分页、面包屑、头像占位等 Li&Pass 无对应场景，不引入死代码；
- 动效纪律、`prefers-reduced-motion`、生产 CSP 不变；
- 不改任何后端/API/OIDC 契约，不触碰认证链路。

## 3. 方案与取舍

### 3.1 令牌层（`frontend/src/index.css`）

- `:root`：muted/success/warning/destructive 换成 V1.3 AA 调校值；
- `.dark`：新增 `--portal-{primary,success,warning,destructive}-soft-solid` 与 `-soft-fg`（值取模板 V1.4）；
- `.dark .badge-*`：改用 `var(--portal-*-soft-solid)` / `var(--portal-*-soft-fg)`；
- 新增 `.select` / `.select-sm`（含 `.select option`）、`input[type="checkbox"|"radio"]`、`input[type="file"]::file-selector-button`、`.table-empty-row` 类。

### 3.2 组件层

- 7 处 `<select className="input-sm ...">` 改为 `select-sm`（宽度工具类保留）；
- 删除复选/单选上的 `h-4 w-4`（由全局 18px 规则接管），保留/补充 `cursor-pointer`；
- 头像文件输入移除 `file:` 工具类，交给全局文件按钮规则；
- `AdminUsersPanel` 空行套 `.table-empty-row`。

### 3.3 取舍

- 进度条、头像、Toast 进度等已有视觉与模板一致或属项目特有模式，不重写；
- 自定义下拉/菜单/分页/面包屑等模板控件 Li&Pass 当前无使用场景，不落地（符合「只移植需要的组件」）；
- 历史 spec（2026-08-17）保留为决策记录，不追溯改写；现状文档（BRAND/MASTER/DESIGN-SOLUTION/CHANGELOG）同步更新。

## 4. 接口与数据模型

无 API、数据库、OIDC 或环境变量变更。对外可见变化仅限 CSS 类与组件类名，语义类（`text-muted` / `bg-success-soft` 等）不变。

## 5. 安全影响

- 不引入第三方脚本/字体/远程资源，不修改 CSP；
- 不动会话、Cookie、认证流程；
- 对比度提升属无障碍加固，无新攻击面。

## 6. UI 设计落地

落地位置与验收对照：

| 文件 | 改动 |
| --- | --- |
| `frontend/src/index.css` | 语义色调校、soft-solid/soft-fg 令牌、`.select`/`.select-sm`、复选/单选、文件按钮、`.table-empty-row` |
| `frontend/src/pages/Admin{Settings,Users,Audit}Panel.tsx`、`AdminClientsPage.tsx`、`AdminNotificationsPanel.tsx` | select 换 `select-sm`；复选/单选去 `h-4 w-4`；标签补 `cursor-pointer` |
| `frontend/src/pages/DashboardPage.tsx` | 文件输入改全局样式；邮件通知标签补 `cursor-pointer` |
| `design-system/lipass/BRAND.md` / `MASTER.md` / `DESIGN-SOLUTION.md` | 色值表、软底令牌表、控件清单同步 |
| `CHANGELOG.md` | 未发布（开发中）功能分区补记 |

## 7. 验收标准

- [ ] `frontend/src/index.css` 无旧语义色残留（`#71807A`/`#2F8F5F`/`#A16207`/`#CF3D3D`）；
- [ ] `.dark` 含 8 个 `*-soft-solid` / `*-soft-fg` 令牌，`badge-*` 引用之；
- [ ] 全部 `<select>` 使用 `select-sm`；复选/单选无 `h-4 w-4`；文件输入无 `file:` 工具类；
- [ ] `AdminUsersPanel` 空行套 `.table-empty-row`；
- [ ] 新语义色/软底组合对比度 ≥ 4.5:1（软底组合 ≥ 8:1，数值见模板索引 §2.2/§2.3）；
- [ ] `cd frontend && npx tsc -b && npm run lint && npm test && npm run build` 全绿；
- [ ] BRAND.md / MASTER.md / DESIGN-SOLUTION.md / CHANGELOG.md 与代码一致。
