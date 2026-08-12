# 交互动效与请求反馈闭环设计

- 日期：2026-08-13
- 状态：待用户评审
- 范围：前端交互细节打磨（`frontend/src`）
- 技术栈：React 19 + TypeScript + Tailwind CSS 4，无新增第三方依赖

## 1. 目标

在现有动效与 Toast 体系基础上补齐五类交互反馈，并形成统一的请求状态闭环：

1. 按钮波纹：点击时有从触点扩散的视觉反馈。
2. 数字滚动：数据加载后，数量类文本以短促 ease-out 动画滚动到位。
3. 消息通知与操作反馈：Toast 入场更有质感；主操作按钮具备 pending/success/error 三态反馈。
4. 数据更新呼吸感：数据刷新或批量操作后，受影响区域一次性轻微呼吸，不循环。
5. 请求状态 UI 闭环：所有主操作统一 `idle → pending → success/error` 状态机，防重复提交、失败可重试、成功自动复位。

非目标：不改动后端 API、不引入动画库（GSAP/Motion 等）、不重做品牌视觉、不做移动端触感反馈（navigator.vibrate）。

## 2. 设计原则

- 动效时长：微交互 150–300ms，数字滚动 ≤ 600ms，呼吸动画 ≤ 800ms。
- 只动 `transform`/`opacity`（波纹用 `transform: scale`，呼吸用 `opacity` + 轻微 `scale`），避免重排。
- 尊重 `prefers-reduced-motion`：动画全部缩短/禁用。
- 用 SVG/内置图标，不用 emoji；可点击元素保持 `cursor-pointer` 与可见 focus。
- 基础件放 `frontend/src/components/` 与 `frontend/src/hooks/`，页面只做接线，不复制实现。

## 3. 组件与模块设计

### 3.1 按钮波纹（`frontend/src/lib/ripple.ts` + `frontend/src/index.css`）

用事件委托实现，不要求改造每个 `<button>`：

- 监听 `pointerdown`，命中 `.btn`（不含 `.btn-link`、`.toast-action` 等小按钮）后在触点坐标插入 `<span class="btn-ripple">`。
- 波纹为绝对定位圆形，`transform: scale(0) → scale(1)` + `opacity` 消退，`animationend` 后移除节点。
- `prefers-reduced-motion: reduce` 时不插入波纹。
- 按钮本身已有 `overflow: hidden`；波纹不拦截点击（`pointer-events: none`）。
- 只允许同一时刻最多 1 个波纹节点，避免快速连点时 DOM 堆积。

### 3.2 数字滚动（`frontend/src/components/AnimatedNumber.tsx`）

- Props：`value: number`、`duration?`（默认 600）、`format?`（默认 `Intl.NumberFormat("zh-CN")`）。
- 用 `requestAnimationFrame` 从旧值插值到新值，easeOutCubic；卸载时取消帧。
- `prefers-reduced-motion` 时直接渲染目标值。
- 首次挂载不做滚动（避免页面载入时所有数字同时滚动），仅 `value` 变化时滚动。
- 应用到：用户中心「N 个会话 / N 个授权网站」，后台用户/应用列表头部「共 N 个」计数。

### 3.3 请求状态机（`frontend/src/hooks/useAsyncAction.ts`）

```ts
type AsyncStatus = "idle" | "pending" | "success" | "error";

function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  options?: {
    minimumPendingMs?: number; // 默认 350，避免一闪而过的 loading
    successResetMs?: number;   // 默认 1600
    onSuccess?: (result: TResult) => void;
    onError?: (err: Error) => void;
  }
): {
  run: (...args: TArgs) => Promise<TResult | undefined>;
  status: AsyncStatus;
  pending: boolean;
  error: Error | null;
  reset: () => void;
};
```

行为：

- `run` 执行期间置 `pending` 并返回 Promise；调用方 `await` 后可自行跳转/关弹窗。
- 成功置 `success`，`successResetMs` 后回到 `idle`；失败置 `error` 并立即回到 `idle`（按钮恢复可点击）。
- 提供 `onSuccess`/`onError` 默认接线到 Toast：成功 `toast.success`，失败 `toast.error`。
- 组件卸载后不 setState。

### 3.4 异步按钮（`frontend/src/components/AsyncButton.tsx`）

包装原生 `<button>`，Props 兼容 `React.ButtonHTMLAttributes`，额外接受：

- `status: AsyncStatus`
- `successLabel?`（默认「已完成」）、`loadingLabel?`（默认「处理中…」）
- `spinner?: boolean`（默认 true）

状态表现：

- `idle`：正常按钮样式与文案。
- `pending`：禁用 + 内联 spinner（CSS 旋转圆环）+ loading 文案。
- `success`：禁用 + 内联 ✓ 图标 + success 文案，浅绿背景一闪。
- `error`：恢复可点击，保留原文案；错误说明由 Toast/就近提示承担。

### 3.5 数据更新呼吸（`frontend/src/hooks/useBreathOnChange.ts` + CSS）

- Hook 签名：`useBreathOnChange<T>(value: T): boolean`；`value` 变化时返回 `true`，800ms 后复位。
- 组件将返回值拼进 `animate-breath` 类；`@keyframes breath` 做一次 `opacity 0.65 ↔ 1` + `scale(0.997 ↔ 1)`。
- 应用到：后台用户/应用列表刷新或批量操作后（表格外壳 + 计数），用户中心数据重新拉取后（会话/应用卡片列表）。
- 首次加载不触发呼吸。

### 3.6 Toast 增强（`frontend/src/components/ToastProvider.tsx` + `index.css`）

- 保留现有 Toast API、自动关闭、悬停暂停进度条、action 按钮。
- 新增：`toast-icon` 入场弹跳（scale 0.6 → 1，150ms），成功/错误图标延续现有 `StatusIcon`。
- 新增：Toast 入场时对同类型 Toast 做轻微位移错开，避免叠放生硬。
- 不改 Toast 自动时长与层级。

## 4. 接入范围（全部主操作按钮）

| 页面 | 接入点 |
| --- | --- |
| 登录 | 登录按钮、2FA 验证按钮、获取/重发验证码 |
| 注册 / 邀请注册 | 注册 / 完成注册按钮 |
| 找回 / 重置密码 | 发送重置验证码、重置密码、重发验证码 |
| 验证邮箱 | 验证、重发验证码 |
| 授权确认 | 同意授权、拒绝 |
| 用户中心 | 保存资料、修改密码、开启/关闭/验证 2FA、退出其他会话、注销账号 |
| 后台用户 | 创建账号、邀请注册、批量启用/禁用/删除、重置密码、重置 2FA |
| 后台应用 | 新建/编辑/删除应用、重置凭据、封禁/解封 |
| 后台设置 | 开启/关闭公开注册 |
| 后台审计 | 无写操作；数据刷新时接入呼吸动画（可选） |

每个接入点遵循同一模式：

```tsx
const action = useAsyncAction(submitFn, { onSuccess, onError });
<AsyncButton status={action.status} onClick={() => action.run(data)}>
  登录
</AsyncButton>
```

## 5. 数据流与错误处理

- 所有异步操作仍由页面原有 `async` 函数发起；`useAsyncAction` 只接管状态展示与反馈，不改变 API 调用。
- 成功 Toast 由 `onSuccess` 统一输出；错误优先使用后端返回的 `Error.message`。
- 需要“成功后关闭弹窗/跳转”的操作在 `await action.run()` 后由页面自行处理，不依赖组件内部。
- 禁用状态防重复提交；弹窗（Modal）内按钮同样适用。

## 6. 可访问性与性能

- `aria-busy` 在 pending 时置 true；spinner 使用 `aria-hidden`，文案承担语义。
- 所有动画在 `prefers-reduced-motion` 下禁用或缩短为 0.01ms（全局已有兜底）。
- 波纹节点用 `contain` 限定绘制范围，动画结束后移除。
- 数字滚动只动画数值文本，不触发布局抖动；长列表不引入额外 DOM 开销。
- 不新增远程依赖，保持包体积不变。

## 7. 验证

- `npx tsc -b`、`npm run lint`、`npm run build` 通过。
- 人工走查：登录失败→按钮恢复并 Toast 报错；登录成功→按钮显示 ✓ 后跳转；后台批量操作→表格呼吸 + 计数滚动；快速连点→只触发一次请求。
- 如浏览器工具可用，截图对比明暗两态下的按钮三态与 Toast 表现。

## 8. 实现顺序

1. CSS 基础：波纹、spinner、breath、Toast 入场增强。
2. `useAsyncAction` + `AsyncButton`。
3. `AnimatedNumber` + 计数接入。
4. 认证页与授权页迁移。
5. 用户中心与后台迁移。
6. `useBreathOnChange` 接入数据刷新区域。
7. 全量验证（typecheck / lint / build / 人工走查）。
