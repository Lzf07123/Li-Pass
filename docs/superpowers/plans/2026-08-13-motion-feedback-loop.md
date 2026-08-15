# 交互动效与请求反馈闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Li&Pass 前端补齐按钮波纹、数字滚动、Toast 增强、数据刷新呼吸动画与统一的请求状态闭环。

**Architecture:** 全部能力做成可复用基础件（`ripple.ts`、`useAsyncAction`、`AsyncButton`、`AnimatedNumber`、`useBreathOnChange`），再由认证页、用户中心、管理后台逐个接线。不引入第三方依赖，动效只操作 `transform`/`opacity`。

**Tech Stack:** React 19 + TypeScript + Tailwind CSS 4 + Vitest + React Testing Library。

## Global Constraints

- 不新增 npm 依赖；不修改后端。
- 动效时长：微交互 150–300ms，数字滚动 ≤ 600ms，呼吸 ≤ 800ms。
- 必须遵守 `prefers-reduced-motion: reduce`（全局 CSS 已把动画缩到 0.01ms，JS 侧也要跳过/缩短）。
- 所有异步按钮防重复提交；pending 时 `aria-busy="true"`。
- 不把 emoji 当图标；状态图标继续使用 `StatusIcon`。
- 不要 `git add -A`；每步只暂存本任务列出的文件，避免把尚未提交的 `AuthSkeleton.tsx`/`PageSkeleton.tsx` 等无关改动带进本计划提交。
- 仓库约定测试不入库：`frontend/src/test/` 与 `frontend/src/__tests__/` 被根 `.gitignore` 第 77-78 行忽略。测试文件只在本地创建并运行验证，**提交时不要 `git add` 测试文件**（否则会报 pathspec ignored）。
- 提交信息用中文 `feat:` / `test:` 前缀，风格与仓库历史一致。

---

### Task 1: 按钮波纹

**Files:**
- Create: `frontend/src/lib/ripple.ts`
- Create: `frontend/src/__tests__/ripple.test.ts`
- Modify: `frontend/src/index.css:183-195`（`.btn` 增加 `relative overflow-hidden`）
- Modify: `frontend/src/index.css:560-610`（新增 `@keyframes btn-ripple` 与 `.btn-ripple`）
- Modify: `frontend/src/main.tsx`（引入并调用 `initRipple`）

**Interfaces:**
- Consumes: 无
- Produces: `initRipple(): void` —— 幂等初始化全局 `pointerdown` 委托；`resetRippleForTests(): void` —— 仅测试用。

- [ ] **Step 1: 写失败测试**

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";

import { initRipple, resetRippleForTests } from "../lib/ripple";

describe("ripple", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    resetRippleForTests();
    vi.restoreAllMocks();
  });

  it("pointerdown 命中 .btn 时插入波纹节点，动画结束后移除", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn() }),
    );
    document.body.innerHTML = '<button class="btn">登录</button>';
    initRipple();

    const btn = document.querySelector<HTMLButtonElement>(".btn")!;
    btn.dispatchEvent(
      new MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10 }),
    );

    const ripple = btn.querySelector(".btn-ripple");
    expect(ripple).not.toBeNull();

    ripple!.dispatchEvent(new Event("animationend"));
    expect(btn.querySelector(".btn-ripple")).toBeNull();
  });

  it("reduced-motion 时不插入波纹", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn() }),
    );
    document.body.innerHTML = '<button class="btn">登录</button>';
    initRipple();

    document
      .querySelector<HTMLButtonElement>(".btn")!
      .dispatchEvent(
        new MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10 }),
      );

    expect(document.querySelector(".btn-ripple")).toBeNull();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- ripple.test.tsx`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 ripple 模块**

```ts
const RIPPLE_CLASS = "btn-ripple";

function createRipple(event: PointerEvent): void {
  const target = event.target as Element | null;
  if (!target) return;
  const btn = target.closest<HTMLElement>(".btn");
  if (!btn) return;
  if (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return;
  }

  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 2;
  btn.querySelector(`.${RIPPLE_CLASS}`)?.remove();

  const ripple = document.createElement("span");
  ripple.className = RIPPLE_CLASS;
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
  ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
  ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
  btn.appendChild(ripple);
}

let initialized = false;

export function initRipple(): void {
  if (initialized || typeof document === "undefined") return;
  initialized = true;
  document.addEventListener("pointerdown", createRipple, { passive: true });
}

/** 仅测试用：重置初始化状态。 */
export function resetRippleForTests(): void {
  initialized = false;
}
```

- [ ] **Step 4: 添加 CSS**

在 `frontend/src/index.css` 的 `.btn` 规则中补充：

```css
  .btn {
    @apply inline-flex cursor-pointer select-none items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium leading-none disabled:pointer-events-none disabled:opacity-50 relative overflow-hidden;
```

在 `@layer utilities` 中新增：

```css
  @keyframes btn-ripple {
    from {
      opacity: 0.45;
      transform: scale(0);
    }
    to {
      opacity: 0;
      transform: scale(1);
    }
  }

  .btn-ripple {
    position: absolute;
    border-radius: 9999px;
    pointer-events: none;
    background: rgba(255, 255, 255, 0.45);
    animation: btn-ripple 550ms var(--ease-out) forwards;
    will-change: transform, opacity;
  }
  .dark .btn-ripple {
    background: rgba(148, 163, 184, 0.28);
  }
  @media (prefers-reduced-motion: reduce) {
    .btn-ripple {
      display: none;
    }
  }
```

- [ ] **Step 5: 在 main.tsx 初始化**

```tsx
import { initRipple } from "./lib/ripple";
// 在 applyBrandAssets() 之后、createRoot 之前调用：
initRipple();
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npm test -- ripple.test.tsx`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/lib/ripple.ts frontend/src/index.css frontend/src/main.tsx
git commit -m "feat: 按钮点击波纹与 reduced-motion 降级"
```

---

### Task 2: Toast 入场增强

**Files:**
- Modify: `frontend/src/index.css:330-430`（`.toast-icon` 增加入场弹跳；`.toast-enter` 增加延迟变量）
- Modify: `frontend/src/components/ToastProvider.tsx`（给 toast 加 `--toast-index` 变量）
- Create: `frontend/src/__tests__/ToastProvider.test.tsx`

**Interfaces:**
- Consumes: 现有 `ToastContext`/`ToastProvider` API
- Produces: 无新接口；仅视觉增强

- [ ] **Step 1: 写失败测试**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToastProvider } from "../components/ToastProvider";
import { useToast } from "../hooks/useToast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.success("已保存")}>
      触发
    </button>
  );
}

describe("ToastProvider", () => {
  it("渲染 success Toast 并带图标容器", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "触发" }));
    expect(screen.getByText("已保存")).toBeInTheDocument();
    expect(document.querySelector(".toast-icon")).not.toBeNull();
    expect(document.querySelector(".toast-icon")?.classList.contains("toast-icon-pop")).toBe(true);
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- ToastProvider.test.tsx`
Expected: FAIL（`toast-icon-pop` 类不存在）

- [ ] **Step 3: ToastProvider 传入索引变量**

把 `toasts.map((toast) => (` 改为：

```tsx
{toasts.map((toast, index) => (
  <div
    key={toast.id}
    role={toast.type === "error" ? "alert" : "status"}
    style={{ "--toast-index": index } as CSSProperties}
    className={`toast toast-${toast.type} ${
      toast.leaving ? "toast-leave" : "toast-enter"
    }`}
  >
    <span className="toast-icon toast-icon-pop">
      <StatusIcon type={toast.type} className="h-4.5 w-4.5" />
    </span>
```

文件顶部增加 `import type { CSSProperties } from "react";`，并在 style 处断言：

```tsx
style={{ "--toast-index": index } as CSSProperties}
```

- [ ] **Step 4: 添加 CSS**

```css
  .toast-icon {
    @apply flex h-8 w-8 shrink-0 items-center justify-center rounded-full;
  }
  .toast-icon-pop {
    animation: toast-icon-pop 180ms var(--ease-spring) both;
  }
  .toast-enter {
    animation: toast-in 320ms var(--ease-spring) both;
    animation-delay: calc(var(--toast-index, 0) * 40ms);
  }

  @keyframes toast-icon-pop {
    from {
      transform: scale(0.5);
      opacity: 0;
    }
    to {
      transform: scale(1);
      opacity: 1;
    }
  }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm test -- ToastProvider.test.tsx`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/index.css frontend/src/components/ToastProvider.tsx
git commit -m "feat: Toast 图标弹跳与入场错峰"
```

---

### Task 3: 请求状态闭环基础件

**Files:**
- Create: `frontend/src/hooks/useAsyncAction.ts`
- Create: `frontend/src/components/AsyncButton.tsx`
- Create: `frontend/src/__tests__/useAsyncAction.test.tsx`
- Create: `frontend/src/__tests__/AsyncButton.test.tsx`
- Modify: `frontend/src/index.css`（新增 `.spinner`、`.btn-success-flash`、`@keyframes portal-spin`）

**Interfaces:**
- Consumes: 无
- Produces:
  - `type AsyncStatus = "idle" | "pending" | "success" | "error"`
  - `function useAsyncAction<TArgs extends unknown[], TResult>(fn: (...args: TArgs) => Promise<TResult>, options?: { minimumPendingMs?: number; successResetMs?: number; onSuccess?: (result: TResult) => void; onError?: (error: Error) => void; }): { run: (...args: TArgs) => Promise<TResult | undefined>; status: AsyncStatus; pending: boolean; error: Error | null; reset: () => void }`
  - `<AsyncButton status="idle" ...>内容</AsyncButton>`，Props 兼容 `ButtonHTMLAttributes<HTMLButtonElement>`，额外 `loadingLabel`/`successLabel`/`spinner`

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/useAsyncAction.test.tsx`：

```tsx
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAsyncAction } from "../hooks/useAsyncAction";

describe("useAsyncAction", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("依次进入 pending → success，并在 successResetMs 后回到 idle", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async (n: number) => n * 2, {
        minimumPendingMs: 0,
        successResetMs: 1000,
      }),
    );

    let promise!: Promise<number | undefined>;
    act(() => {
      promise = result.current.run(4);
    });
    expect(result.current.status).toBe("pending");

    await act(async () => {
      await promise;
    });
    expect(result.current.status).toBe("success");
    expect(result.current.pending).toBe(false);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.status).toBe("idle");
  });

  it("失败时进入 error 并触发 onError，随后自动复位", async () => {
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useAsyncAction(
        async () => {
          throw new Error("boom");
        },
        { onError, minimumPendingMs: 0 },
      ),
    );

    let promise!: Promise<number | undefined>;
    act(() => {
      promise = result.current.run();
    });
    await act(async () => {
      await promise;
    });
    expect(result.current.status).toBe("error");
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "boom" }));

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(result.current.status).toBe("idle");
  });

  it("pending 期间再次 run 直接返回 undefined", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async () => "ok", { minimumPendingMs: 100 }),
    );
    let first!: Promise<string | undefined>;
    act(() => {
      first = result.current.run();
    });
    const second = result.current.run();
    expect(second).resolves.toBeUndefined();
    await act(async () => {
      await first;
    });
  });
});
```

`frontend/src/__tests__/AsyncButton.test.tsx`：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AsyncButton } from "../components/AsyncButton";

describe("AsyncButton", () => {
  it("pending 时禁用并显示 spinner 与 loading 文案", () => {
    render(
      <AsyncButton status="pending" loadingLabel="提交中…">
        提交
      </AsyncButton>,
    );
    const btn = screen.getByRole("button", { name: "提交中…" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(document.querySelector(".spinner")).not.toBeNull();
  });

  it("success 时显示成功文案并禁用", () => {
    render(
      <AsyncButton status="success" successLabel="已保存">
        保存
      </AsyncButton>,
    );
    const btn = screen.getByRole("button", { name: "已保存" });
    expect(btn).toBeDisabled();
    expect(btn.className).toContain("btn-success-flash");
  });

  it("idle 时透传 children", () => {
    render(<AsyncButton status="idle">登录</AsyncButton>);
    expect(screen.getByRole("button", { name: "登录" })).toBeEnabled();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- useAsyncAction.test.tsx AsyncButton.test.tsx`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 useAsyncAction**

```ts
import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncStatus = "idle" | "pending" | "success" | "error";

interface UseAsyncActionOptions<TResult> {
  minimumPendingMs?: number;
  successResetMs?: number;
  onSuccess?: (result: TResult) => void;
  onError?: (error: Error) => void;
}

export function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  options: UseAsyncActionOptions<TResult> = {},
) {
  const {
    minimumPendingMs = 350,
    successResetMs = 1600,
    onSuccess,
    onError,
  } = options;
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  const mounted = useRef(true);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      timers.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | undefined> => {
      if (status === "pending") return undefined;
      const startedAt = Date.now();
      setStatus("pending");
      setError(null);
      try {
        const result = await fn(...args);
        const elapsed = Date.now() - startedAt;
        const wait = Math.max(0, minimumPendingMs - elapsed);
        if (wait > 0) {
          await new Promise((resolve) => setTimeout(resolve, wait));
        }
        if (!mounted.current) return undefined;
        setStatus("success");
        onSuccess?.(result);
        timers.current.push(
          setTimeout(() => {
            if (mounted.current) reset();
          }, successResetMs),
        );
        return result;
      } catch (err) {
        const failure = err instanceof Error ? err : new Error(String(err));
        if (!mounted.current) return undefined;
        setStatus("error");
        setError(failure);
        onError?.(failure);
        timers.current.push(
          setTimeout(() => {
            if (mounted.current) reset();
          }, 800),
        );
        return undefined;
      }
    },
    [fn, minimumPendingMs, successResetMs, onError, onSuccess, reset, status],
  );

  return { run, status, pending: status === "pending", error, reset };
}
```

- [ ] **Step 4: 实现 AsyncButton**

```tsx
import type { ButtonHTMLAttributes, ReactNode } from "react";

import type { AsyncStatus } from "../hooks/useAsyncAction";

interface AsyncButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  status: AsyncStatus;
  loadingLabel?: string;
  successLabel?: string;
  spinner?: boolean;
  children: ReactNode;
}

const STATUS_CLASS: Record<AsyncStatus, string> = {
  idle: "",
  pending: "opacity-80",
  success: "btn-success-flash",
  error: "",
};

export function AsyncButton({
  status,
  loadingLabel = "处理中…",
  successLabel = "已完成",
  spinner = true,
  children,
  disabled,
  className = "",
  ...rest
}: AsyncButtonProps) {
  const label =
    status === "pending"
      ? loadingLabel
      : status === "success"
        ? successLabel
        : children;

  return (
    <button
      {...rest}
      disabled={disabled || status === "pending" || status === "success"}
      aria-busy={status === "pending" || undefined}
      className={`${className} ${STATUS_CLASS[status]}`.trim()}
    >
      {spinner && status === "pending" && (
        <span aria-hidden="true" className="spinner" />
      )}
      {label}
    </button>
  );
}
```

- [ ] **Step 5: 添加 CSS**

```css
  @keyframes portal-spin {
    to {
      transform: rotate(360deg);
    }
  }
  .spinner {
    display: inline-block;
    height: 1rem;
    width: 1rem;
    border-radius: 9999px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    animation: portal-spin 0.8s linear infinite;
  }
  .btn-success-flash {
    background: var(--portal-success);
    color: #ffffff;
  }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npm test -- useAsyncAction.test.tsx AsyncButton.test.tsx`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/hooks/useAsyncAction.ts frontend/src/components/AsyncButton.tsx frontend/src/index.css
git commit -m "feat: 请求状态机 useAsyncAction 与 AsyncButton 三态反馈"
```

---

### Task 4: 数字滚动与数据刷新呼吸

**Files:**
- Create: `frontend/src/components/AnimatedNumber.tsx`
- Create: `frontend/src/hooks/useBreathOnChange.ts`
- Create: `frontend/src/__tests__/AnimatedNumber.test.tsx`
- Create: `frontend/src/__tests__/useBreathOnChange.test.tsx`
- Modify: `frontend/src/index.css`（新增 `@keyframes portal-breath` 与 `.animate-breath`）

**Interfaces:**
- Produces:
  - `<AnimatedNumber value={number} duration?={600} format?={(n: number) => string} />`
  - `function useBreathOnChange<T>(value: T, durationMs?: number): boolean`

- [ ] **Step 1: 写失败测试**

`frontend/src/__tests__/AnimatedNumber.test.tsx`：

```tsx
import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnimatedNumber } from "../components/AnimatedNumber";

function installRaf() {
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    return window.setTimeout(() => cb(performance.now()), 16);
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id));
}

describe("AnimatedNumber", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("reduced-motion 时直接显示目标值", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn() }),
    );
    render(<AnimatedNumber value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("数值变化后滚动到目标值", () => {
    installRaf();
    vi.useFakeTimers();
    const { rerender } = render(<AnimatedNumber value={0} />);
    rerender(<AnimatedNumber value={100} />);
    act(() => {
      vi.advanceTimersByTime(700);
    });
    expect(screen.getByText("100")).toBeInTheDocument();
  });
});
```

`frontend/src/__tests__/useBreathOnChange.test.tsx`：

```tsx
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useBreathOnChange } from "../hooks/useBreathOnChange";

describe("useBreathOnChange", () => {
  it("value 变化后返回 true，超时后复位", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }: { value: number }) => useBreathOnChange(value),
      { initialProps: { value: 1 } },
    );
    expect(result.current).toBe(false);

    rerender({ value: 2 });
    expect(result.current).toBe(true);

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(result.current).toBe(false);
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- AnimatedNumber.test.tsx useBreathOnChange.test.tsx`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 AnimatedNumber**

```tsx
import { useEffect, useRef, useState } from "react";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  format?: (value: number) => string;
}

const defaultFormat = new Intl.NumberFormat("zh-CN");

export function AnimatedNumber({
  value,
  duration = 600,
  format,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);
  const frame = useRef<number | null>(null);
  const formatter = format ?? ((n: number) => defaultFormat.format(n));

  useEffect(() => {
    if (value === previous.current) return;
    if (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setDisplay(value);
      previous.current = value;
      return;
    }

    const from = previous.current;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        previous.current = value;
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [duration, value]);

  return <span>{formatter(display)}</span>;
}
```

- [ ] **Step 4: 实现 useBreathOnChange**

```ts
import { useEffect, useRef, useState } from "react";

export function useBreathOnChange<T>(value: T, durationMs = 800): boolean {
  const [breathing, setBreathing] = useState(false);
  const previous = useRef(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (Object.is(previous.current, value)) return;
    previous.current = value;
    setBreathing(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setBreathing(false), durationMs);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [durationMs, value]);

  return breathing;
}
```

- [ ] **Step 5: 添加 CSS**

```css
  @keyframes portal-breath {
    0%,
    100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.72;
      transform: scale(0.997);
    }
  }
  .animate-breath {
    animation: portal-breath 800ms var(--ease-out) both;
  }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npm test -- AnimatedNumber.test.tsx useBreathOnChange.test.tsx`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add frontend/src/components/AnimatedNumber.tsx frontend/src/hooks/useBreathOnChange.ts frontend/src/index.css
git commit -m "feat: 数字滚动组件与数据更新呼吸动画 Hook"
```

---

### Task 5: 认证页与授权页迁移

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/pages/RegisterPage.tsx`
- Modify: `frontend/src/pages/InviteRegisterPage.tsx`
- Modify: `frontend/src/pages/ForgotPasswordPage.tsx`
- Modify: `frontend/src/pages/ResetPasswordPage.tsx`
- Modify: `frontend/src/pages/VerifyEmailPage.tsx`
- Modify: `frontend/src/pages/ConsentPage.tsx`

**Interfaces:**
- Consumes: `useAsyncAction`、`AsyncButton`（Task 3）
- Produces: 认证/授权页所有提交按钮具备 pending/success/error 闭环

统一模式（每个页面都按此模式改）：

```tsx
const action = useAsyncAction(
  async (...payload) => {
    // 原 async 函数体（去掉 setBusy/finally）
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") },
);

async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();
  await action.run(...payload);
}

<AsyncButton type="submit" status={action.status}>提交</AsyncButton>
```

- [ ] **Step 1: LoginPage**

把 `handleSubmit`、`verifyCode`、`sendCode` 改为上面模式，移除 `verifying`/`sending` state，改用对应 action 的 `pending`：

```tsx
const loginAction = useAsyncAction(
  async (email: string, password: string, rememberMe: boolean) => {
    const result = await authApi.login({ email, password, remember_me: rememberMe });
    if (result.requires_2fa && result.challenge_id) {
      const methods = result.methods ?? [];
      setChallenge({ id: result.challenge_id, methods });
      setEmailStatus(result.email_status ?? null);
      setResendCountdown(0);
      setEmailRetryAfterSeconds(result.email_retry_after_seconds ?? 3600);
      setMethod(
        methods.includes("email_otp")
          ? "email_otp"
          : methods.includes("totp")
            ? "totp"
            : "recovery",
      );
    } else if (next) {
      window.location.href = next;
    } else {
      navigate("/");
    }
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "登录失败") },
);

const verifyAction = useAsyncAction(
  async (challengeId: string, method: string, code: string) => {
    await auth2faApi.verify(challengeId, method, code);
    if (next) window.location.href = next;
    else navigate("/");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "验证失败") },
);

const sendCodeAction = useAsyncAction(
  async (challengeId: string) => {
    await auth2faApi.send(challengeId);
    setEmailStatus("sent");
    setResendCountdown(60);
    toast.success("验证码已发送，请查收邮箱");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "发送失败") },
);
```

按钮替换：

```tsx
<AsyncButton type="submit" status={loginAction.status}>登录</AsyncButton>
<AsyncButton type="submit" status={verifyAction.status}>验证</AsyncButton>
<AsyncButton
  type="button"
  status={sendCodeAction.status}
  disabled={resendCountdown > 0}
  onClick={() => void sendCodeAction.run(challenge.id)}
>
  {resendCountdown > 0
    ? `重新发送（${resendCountdown}s）`
    : emailStatus === "sent"
      ? "重新发送邮箱验证码"
      : "获取邮箱验证码"}
</AsyncButton>
```

注意 `sendCode` 按钮原 `disabled={verifying || sending || ...}` 改为 `disabled={verifyAction.pending || resendCountdown > 0}`；`verify` 按钮的 `disabled={verifying}` 一并删除（AsyncButton 自带）。

- [ ] **Step 2: RegisterPage / InviteRegisterPage**

```tsx
// RegisterPage
const submitAction = useAsyncAction(
  async (email: string, nickname: string, password: string) => {
    await authApi.register({ email, nickname, password });
    navigate(`/verify-email?email=${encodeURIComponent(email)}`);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "注册失败") },
);
<AsyncButton type="submit" status={submitAction.status}>注册</AsyncButton>
```

```tsx
// InviteRegisterPage：删除 busy state
const submitAction = useAsyncAction(
  async (nickname: string, password: string) => {
    const result = await authApi.registerByInvite({ token, nickname, password });
    toast.success(result.message);
    navigate("/login");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "注册失败") },
);
<AsyncButton type="submit" status={submitAction.status}>完成注册</AsyncButton>
```

注册页保留原表单校验（密码长度等）在 `handleSubmit` 里先做，再 `await submitAction.run(...)`。

- [ ] **Step 3: ForgotPasswordPage / ResetPasswordPage / VerifyEmailPage**

```tsx
// ForgotPasswordPage
const submitAction = useAsyncAction(
  async (email: string) => {
    const result = await authApi.requestPasswordReset({ email });
    toast.success(result.message, {
      duration: 8000,
      action: { label: "去设置新密码", onClick: () => navigate(`/reset-password?email=${encodeURIComponent(email)}`) },
    });
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "发送失败") },
);
<AsyncButton type="submit" status={submitAction.status}>发送重置验证码</AsyncButton>
```

```tsx
// ResetPasswordPage：submit 与 resend 各一个 action
const submitAction = useAsyncAction(
  async (email: string, code: string, newPassword: string) => {
    const result = await authApi.confirmPasswordReset({ email, code, new_password: newPassword });
    toast.success(result.message, { duration: 8000, action: { label: "去登录", onClick: () => navigate("/login") } });
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "重置失败") },
);
const resendAction = useAsyncAction(
  async (email: string) => {
    await authApi.requestPasswordReset({ email });
    setResendCountdown(60);
    toast.success("验证码已重新发送");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "重新发送失败") },
);
```

```tsx
// VerifyEmailPage
const submitAction = useAsyncAction(
  async (email: string, code: string) => {
    const result = await authApi.verifyEmail({ email, code });
    toast.success(result.message, { duration: 8000, action: { label: "去登录", onClick: () => navigate("/login") } });
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "验证失败") },
);
const resendAction = useAsyncAction(
  async (email: string) => {
    await authApi.resendVerifyEmail(email);
    setResendCountdown(60);
    toast.success("验证码已重新发送");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "重新发送失败") },
);
```

所有“重发”按钮统一：

```tsx
<AsyncButton
  type="button"
  status={resendAction.status}
  disabled={resendCountdown > 0}
  onClick={() => void resendAction.run(email)}
>
  {resendCountdown > 0 ? `重新发送（${resendCountdown}s）` : "重新发送验证码"}
</AsyncButton>
```

- [ ] **Step 4: ConsentPage**

```tsx
const decideAction = useAsyncAction(
  async (approve: boolean) => {
    const result = approve
      ? await consentApi.approve(requestId)
      : await consentApi.deny(requestId);
    window.location.href = result.redirect_url;
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") },
);

<AsyncButton
  type="button"
  status={decideAction.status}
  className="btn btn-primary flex-1"
  onClick={() => void decideAction.run(true)}
>
  同意授权
</AsyncButton>
<AsyncButton
  type="button"
  status={decideAction.status}
  className="btn btn-secondary flex-1"
  onClick={() => void decideAction.run(false)}
>
  拒绝
</AsyncButton>
```

删除原 `decide` 函数；`requestId` 为空时页面现有逻辑不变（`useEffect` 直接 return）。

- [ ] **Step 5: 运行现有测试**

Run: `npm test -- LoginPage.test.tsx RegisterPage.test.tsx ConsentPage.test.tsx ResetPasswordPage.test.tsx`
Expected: PASS（按钮文案仍为“登录”“注册”“同意授权”等；`waitFor` 兼容 AsyncButton 的 loading 文案）

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/LoginPage.tsx frontend/src/pages/RegisterPage.tsx frontend/src/pages/InviteRegisterPage.tsx frontend/src/pages/ForgotPasswordPage.tsx frontend/src/pages/ResetPasswordPage.tsx frontend/src/pages/VerifyEmailPage.tsx frontend/src/pages/ConsentPage.tsx
git commit -m "feat: 认证页与授权页接入请求状态闭环"
```

---

### Task 6: 用户中心迁移

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/components/ConfirmDialog.tsx`（支持 `status` 传入 `AsyncButton`）

**Interfaces:**
- Consumes: `useAsyncAction`、`AsyncButton`
- Produces: `ConfirmDialog` 新增可选 `status?: AsyncStatus`，优先于 `busy`

- [ ] **Step 1: ConfirmDialog 支持 status**

```tsx
import type { AsyncStatus } from "../hooks/useAsyncAction";
import { AsyncButton } from "./AsyncButton";

// props 增加 status?: AsyncStatus
// footer 确认按钮改为：
<AsyncButton
  type="button"
  status={status ?? (busy ? "pending" : "idle")}
  className={`btn ${intent === "danger" ? "btn-danger" : "btn-primary"}`}
  onClick={onConfirm}
  loadingLabel="处理中…"
>
  {confirmLabel}
</AsyncButton>
```

同时取消按钮 `disabled={busy || status === "pending"}`，`onClose` 守卫改为：

```tsx
onClose={busy || status === "pending" ? () => undefined : onCancel}
```

- [ ] **Step 2: 写 ConfirmDialog 测试**

`frontend/src/__tests__/ConfirmDialog.test.tsx`：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfirmDialog } from "../components/ConfirmDialog";

describe("ConfirmDialog", () => {
  it("status=pending 时确认按钮显示处理中", () => {
    render(
      <ConfirmDialog
        open
        title="删除"
        message="确认？"
        status="pending"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: "处理中…" })).toBeDisabled();
  });
});
```

- [ ] **Step 3: DashboardPage 迁移主操作**

新增（保留原有 state 中的 `twofaBusy` 用于 2FA 多按钮互斥，其它 busy 删除）：

```tsx
const saveProfileAction = useAsyncAction(
  async (nickname: string, avatarUrl: string) => {
    const updated = await meApi.updateProfile({ nickname, avatar_url: avatarUrl || null });
    setUser(updated);
    setNickname(updated.nickname);
    setAvatarUrl(updated.avatar_url ?? "");
    toast.success("资料已保存");
  },
  { onError: (err) => showError(err, "保存失败") },
);

const changePasswordAction = useAsyncAction(
  async (currentPassword: string, newPassword: string) => {
    const result = await meApi.changePassword({ current_password: currentPassword, new_password: newPassword });
    toast.success(result.message);
    setCurrentPassword("");
    setNewPassword("");
  },
  { onError: (err) => showError(err, "修改失败") },
);

const uploadAvatarAction = useAsyncAction(
  async (file: File) => {
    const updated = await meApi.uploadAvatar(file);
    setUser(updated);
    setAvatarUrl(updated.avatar_url ?? "");
    setAvatarFile(null);
    toast.success("头像已更新");
  },
  { onError: (err) => showError(err, "上传失败") },
);

const revokeSessionAction = useAsyncAction(
  async (id: string) => {
    await sessionsApi.revoke(id);
    setSessions(await sessionsApi.list());
    setRevokeSessionId(null);
    toast.success("已退出该设备");
  },
  { onError: (err) => showError(err, "操作失败") },
);

const revokeAppAction = useAsyncAction(
  async (clientId: string, name: string) => {
    const result = await appsApi.revoke(clientId);
    setApps((prev) => prev.filter((app) => app.client_id !== clientId));
    setRevokeTarget(null);
    toast.success(`已取消对“${name}”的授权`);
    if (result.logout_uri) {
      window.location.href = `${result.logout_uri}?next=${encodeURIComponent(`${window.location.origin}/`)}`;
    }
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "取消授权失败") },
);

const deleteAccountAction = useAsyncAction(
  async (password: string) => {
    const result = await meApi.deleteAccount(password);
    setDeleteAccountOpen(false);
    setDeleteAccountPassword("");
    toast.success(result.message);
    navigate("/login");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "注销失败") },
);
```

删除 `revoking`、`deleteAccountBusy` state。按钮替换：

```tsx
<AsyncButton type="submit" status={saveProfileAction.status}>保存</AsyncButton>
<AsyncButton type="submit" status={changePasswordAction.status}>修改密码</AsyncButton>
<AsyncButton type="submit" status={uploadAvatarAction.status}>上传头像</AsyncButton>
<AsyncButton
  type="button"
  status={revokeSessionAction.pending && session.id === revokeSessionId ? "pending" : "idle"}
  disabled={session.current}
  onClick={() => {
    setRevokeSessionId(session.id);
    void revokeSessionAction.run(session.id);
  }}
>
  退出
</AsyncButton>
<ConfirmDialog ... status={revokeAppAction.status} onConfirm={() => revokeTarget && void revokeAppAction.run(revokeTarget.client_id, revokeTarget.name)} />
<AsyncButton type="submit" form="delete-account-form" status={deleteAccountAction.status} className="btn btn-danger">永久注销</AsyncButton>
```

新增 `const [revokeSessionId, setRevokeSessionId] = useState<string | null>(null);`。

2FA 三个入口（邮箱开关、TOTP 设置/启用/关闭）保持 `twofaBusy` 互斥，但按钮换成：

```tsx
<AsyncButton
  type="button"
  status={twofaBusy === "email" ? "pending" : "idle"}
  disabled={twofa === null || twofaBusy !== null}
  onClick={toggleEmailTwofa}
>
  {twofa?.email_otp_enabled ? "关闭" : "开启"}
</AsyncButton>
```

TOTP 三个按钮同理用 `twofaBusy === "totp-setup" / "totp-enable" / "totp-disable"` 作为 status。

- [ ] **Step 4: 运行测试**

Run: `npm test -- DashboardPage.test.tsx DashboardTwofa.test.tsx`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/components/ConfirmDialog.tsx
git commit -m "feat: 用户中心操作按钮接入请求状态闭环"
```

---

### Task 7: 后台用户管理迁移

**Files:**
- Modify: `frontend/src/pages/AdminUsersPanel.tsx`

**Interfaces:**
- Consumes: `useAsyncAction`、`AsyncButton`
- Produces: 表单/弹窗/批量操作全部接入闭环

- [ ] **Step 1: 表单与批量操作迁移**

新增：

```tsx
const resetPasswordAction = useAsyncAction(
  async (id: string, newPassword: string) => {
    const result = await adminUsersApi.resetPassword(id, newPassword);
    toast.success(result.message);
    setPasswordTarget(null);
    setNewPassword("");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "重置失败") },
);

const deleteAction = useAsyncAction(
  async (id: string, password: string) => {
    const result = await adminUsersApi.deleteAccount(id, password);
    setUsers((prev) => prev.filter((item) => item.id !== id));
    setDeleteTarget(null);
    setDeletePassword("");
    toast.success(result.message);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "删除失败") },
);

const createAction = useAsyncAction(
  async (email: string, nickname: string, password: string) => {
    const created = await adminUsersApi.createAccount({ email, nickname, password });
    setCreateOpen(false);
    toast.success(`账号 ${created.email} 已创建，用户可直接登录`);
    load(query, statusFilter, roleFilter);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "创建失败") },
);

const inviteAction = useAsyncAction(
  async (email: string, nickname: string) => {
    const result = await adminUsersApi.invite({ email, nickname: nickname || undefined });
    setInviteOpen(false);
    await load(query, statusFilter, roleFilter);
    toast.success(result.message);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "发送邀请失败") },
);

const batchStatusAction = useAsyncAction(
  async (ids: string[], status: "active" | "disabled") => {
    const result = await adminUsersApi.batchUpdate(ids, { status });
    setSelected(new Set());
    await load(query, statusFilter, roleFilter);
    toast.success(`已${status === "active" ? "启用" : "禁用"} ${result.updated.length} 个账号`);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "批量操作失败") },
);

const batchDeleteAction = useAsyncAction(
  async (ids: string[], password: string) => {
    const result = await adminUsersApi.batchDelete(ids, password);
    setBatchDeleteOpen(false);
    setBatchDeletePassword("");
    setSelected(new Set());
    await load(query, statusFilter, roleFilter);
    toast.success(result.message);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "批量删除失败") },
);

const batchInviteAction = useAsyncAction(
  async (emails: string[]) => {
    const result = await adminUsersApi.batchInvite(emails);
    setBatchInviteOpen(false);
    setBatchInviteText("");
    await load(query, statusFilter, roleFilter);
    const summary = [`已发送 ${result.invited.length} 封邀请`];
    if (result.skipped.length > 0) summary.push(`跳过 ${result.skipped.length} 个（已注册或已邀请）`);
    toast.success(summary.join("，"));
    if (result.failed.length > 0) {
      toast.error(`${result.failed.length} 封发送失败：${result.failed.map((item) => item.email).join("、")}`);
    }
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "批量邀请失败") },
);
```

删除 `deleting`、`createBusy`、`inviteBusy`、`bulkBusy`、`batchInviteBusy` state；保留 `inviteBusyId` 用于行内重发邀请互斥。表单提交函数改为 `event.preventDefault()` 后调用对应 `action.run(...)`。Modal footer 按钮全部改为：

```tsx
<AsyncButton type="submit" form="reset-password-form" status={resetPasswordAction.status} className="btn btn-primary">确认重置</AsyncButton>
<AsyncButton type="submit" form="delete-user-form" status={deleteAction.status} className="btn btn-danger">永久删除</AsyncButton>
<AsyncButton type="submit" form="create-user-form" status={createAction.status} className="btn btn-primary">创建账号</AsyncButton>
<AsyncButton type="submit" form="invite-user-form" status={inviteAction.status} className="btn btn-primary">发送邀请</AsyncButton>
<AsyncButton type="submit" form="batch-delete-user-form" status={batchDeleteAction.status} className="btn btn-danger">永久删除</AsyncButton>
<AsyncButton type="submit" form="batch-invite-user-form" status={batchInviteAction.status} className="btn btn-primary">发送邀请</AsyncButton>
```

批量操作按钮：

```tsx
<AsyncButton
  type="button"
  status={batchStatusAction.pending ? "pending" : "idle"}
  disabled={selected.size === 0}
  className="btn btn-secondary px-2.5 py-1.5 text-xs"
  onClick={() => void batchStatusAction.run(Array.from(selected), "active")}
>
  批量启用
</AsyncButton>
<AsyncButton
  type="button"
  status={batchStatusAction.pending ? "pending" : "idle"}
  disabled={selected.size === 0}
  className="btn btn-secondary px-2.5 py-1.5 text-xs"
  onClick={() => void batchStatusAction.run(Array.from(selected), "disabled")}
>
  批量禁用
</AsyncButton>
```

“批量删除”按钮保持打开弹窗（无异步）；弹窗内由 `batchDeleteAction` 承接。

- [ ] **Step 2: ConfirmDialog 类操作迁移**

`runConfirm` 改为单一 action：

```tsx
const confirmAction = useAsyncAction(
  async (user: AdminUserOut, action: "toggle" | "reset2fa" | "cancelInvite" | "removeInvite") => {
    if (action === "toggle") {
      const nextStatus = user.status === "active" ? "disabled" : "active";
      const updated = await adminUsersApi.update(user.id, { status: nextStatus });
      setUsers((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      toast.success(`${user.email} 已${nextStatus === "active" ? "启用" : "禁用"}`);
    } else if (action === "reset2fa") {
      const result = await adminUsersApi.reset2fa(user.id);
      toast.success(result.message);
    } else if (action === "cancelInvite") {
      const result = await adminUsersApi.cancelInvite(user.id);
      await load(query, statusFilter, roleFilter);
      toast.success(result.message);
    } else {
      const result = await adminUsersApi.deleteInvite(user.id);
      await load(query, statusFilter, roleFilter);
      toast.success(result.message);
    }
    setConfirmTarget(null);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") },
);

<ConfirmDialog
  ...
  status={confirmAction.status}
  onConfirm={() => confirmTarget && void confirmAction.run(confirmTarget.user, confirmTarget.action)}
/>
```

行内“重发邀请”保留 `inviteBusyId`：

```tsx
<AsyncButton
  type="button"
  status={inviteBusyId === user.id ? "pending" : "idle"}
  disabled={inviteBusyId !== null}
  className="btn btn-secondary px-2.5 py-1.5 text-xs"
  onClick={() => void runResendInvite(user)}
>
  重发邀请
</AsyncButton>
```

行内其它按钮（禁用/启用、重置密码、重置 2FA、删除）只负责打开确认/弹窗，不接异步，保持原样。

- [ ] **Step 3: 运行测试**

Run: `npm test -- AdminPage.test.tsx`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/AdminUsersPanel.tsx
git commit -m "feat: 后台用户管理接入请求状态闭环"
```

---

### Task 8: 后台应用与设置迁移

**Files:**
- Modify: `frontend/src/pages/AdminClientsPage.tsx`
- Modify: `frontend/src/pages/AdminSettingsPanel.tsx`

**Interfaces:**
- Consumes: `useAsyncAction`、`AsyncButton`
- Produces: 应用创建/编辑/删除/重置凭据/启停/黑名单、设置开关全部闭环

- [ ] **Step 1: AdminClientsPage**

新增：

```tsx
const createAction = useAsyncAction(
  async (payload: {
    name: string;
    homeUrl: string;
    logoutUri: string;
    redirectUris: string[];
    isPublic: boolean;
  }) => {
    const result = await adminClientsApi.create({
      name: payload.name,
      home_url: payload.homeUrl || null,
      logout_uri: payload.logoutUri || null,
      redirect_uris: payload.redirectUris,
      public: payload.isPublic,
    });
    setClients((prev) => [result.client, ...prev]);
    setSecretModal({
      name: result.client.name,
      client_id: result.client.client_id,
      secret: result.client_secret ?? "",
    });
    setName("");
    setHomeUrl("");
    setLogoutUri("");
    setRedirectUris("");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "创建失败") },
);

const saveEditAction = useAsyncAction(
  async (draft: ClientOut) => {
    const updated = await adminClientsApi.update(draft.id, {
      name: draft.name,
      description: draft.description,
      logo_url: draft.logo_url || null,
      home_url: draft.home_url || null,
      logout_uri: draft.logout_uri || null,
      redirect_uris: draft.redirect_uris,
      scopes: draft.scopes,
      require_consent_every_time: draft.require_consent_every_time,
      is_active: draft.is_active,
    });
    setClients((prev) => prev.map((client) => (client.id === updated.id ? updated : client)));
    setEditingId(null);
    setEditDraft(null);
    toast.success(`应用“${updated.name}”已保存`);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "保存失败") },
);

const removeAction = useAsyncAction(
  async (client: ClientOut) => {
    await adminClientsApi.remove(client.id);
    setClients((prev) => prev.filter((item) => item.id !== client.id));
    setRemoveTarget(null);
    toast.success(`应用“${client.name}”已删除`);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "删除失败") },
);

const resetSecretAction = useAsyncAction(
  async (client: ClientOut) => {
    const result = await adminClientsApi.resetSecret(client.id);
    setResetTarget(null);
    setSecretModal({
      name: client.name,
      client_id: client.client_id,
      secret: result.client_secret ?? "",
    });
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "重置密钥失败") },
);

const toggleAction = useAsyncAction(
  async (client: ClientOut) => {
    const updated = await adminClientsApi.update(client.id, { is_active: !client.is_active });
    setClients((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    toast.success(`应用“${updated.name}”已${updated.is_active ? "启用" : "停用"}`);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") },
);

const blockAction = useAsyncAction(
  async (clientId: string, email: string, reason: string, blockId?: string) => {
    if (blockId) {
      await adminBlocksApi.remove(clientId, blockId);
      setBlocks((prev) => ({
        ...prev,
        [clientId]: (prev[clientId] ?? []).filter((block) => block.id !== blockId),
      }));
    } else {
      const created = await adminBlocksApi.add(clientId, { email, reason });
      setBlocks((prev) => ({
        ...prev,
        [clientId]: [created, ...(prev[clientId] ?? [])],
      }));
      setBlockEmail((prev) => ({ ...prev, [clientId]: "" }));
      setBlockReason((prev) => ({ ...prev, [clientId]: "" }));
    }
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "操作失败") },
);
```

按钮替换：

```tsx
<AsyncButton type="submit" status={createAction.status}>创建应用</AsyncButton>
<AsyncButton type="button" status={saveEditAction.status} className="btn btn-primary" onClick={() => editDraft && void saveEditAction.run(editDraft)}>保存修改</AsyncButton>
<AsyncButton type="button" status={toggleAction.pending ? "pending" : "idle"} className="btn btn-secondary" onClick={() => void toggleAction.run(client)}>{client.is_active ? "停用" : "启用"}</AsyncButton>
<AsyncButton type="button" status={blockAction.pending ? "pending" : "idle"} className="btn btn-danger px-3 py-1.5 text-xs" onClick={() => void blockAction.run(client.id, blockEmail[client.id] ?? "", blockReason[client.id] ?? "")}>封禁</AsyncButton>
```

黑名单“解封”按钮：

```tsx
<AsyncButton
  type="button"
  status={blockAction.pending ? "pending" : "idle"}
  className="btn-link text-sm"
  spinner={false}
  onClick={() => void blockAction.run(client.id, "", "", block.id)}
>
  解封
</AsyncButton>
```

两个 ConfirmDialog：

```tsx
<ConfirmDialog ... status={removeAction.status} onConfirm={() => removeTarget && void removeAction.run(removeTarget)} />
<ConfirmDialog ... status={resetSecretAction.status} onConfirm={() => resetTarget && void resetSecretAction.run(resetTarget)} />
```

行内多个异步按钮共用 `blockAction`/`toggleAction` 时，pending 会同时显示在同类按钮上；可接受（同一时刻只允许一个请求，`useAsyncAction` 已防重入）。

- [ ] **Step 2: AdminSettingsPanel**

```tsx
const toggleAction = useAsyncAction(
  async (settings: SiteSettings) => {
    const next = { public_registration_enabled: !settings.public_registration_enabled };
    const updated = await adminSettingsApi.update(next);
    setSettings(updated);
    toast.success(updated.public_registration_enabled ? "已开启公开注册" : "已关闭公开注册，仅接受邀请注册");
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "保存设置失败") },
);

<AsyncButton
  type="button"
  status={toggleAction.status}
  disabled={settings === null}
  className={`btn ${settings?.public_registration_enabled ? "btn-secondary" : "btn-primary"}`}
  onClick={() => settings && void toggleAction.run(settings)}
>
  {settings?.public_registration_enabled ? "关闭" : "开启"}
</AsyncButton>
```

删除 `busy` state。

- [ ] **Step 3: 运行测试**

Run: `npm test -- AdminClientsPage.test.tsx`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/AdminClientsPage.tsx frontend/src/pages/AdminSettingsPanel.tsx
git commit -m "feat: 后台应用与设置接入请求状态闭环"
```

---

### Task 9: 数字计数与数据刷新呼吸

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/AdminUsersPanel.tsx`
- Modify: `frontend/src/pages/AdminClientsPage.tsx`
- Modify: `frontend/src/pages/AdminAuditPanel.tsx`

**Interfaces:**
- Consumes: `AnimatedNumber`、`useBreathOnChange`
- Produces: 计数滚动 + 数据刷新呼吸

- [ ] **Step 1: Dashboard 计数与呼吸**

```tsx
const sessionsBreathing = useBreathOnChange(sessions);
const appsBreathing = useBreathOnChange(apps);

// 登录设备标题
<h2 className="mb-4 text-base font-semibold text-foreground">
  登录设备
  <span className="ml-2 text-sm font-normal text-muted">
    共 <AnimatedNumber value={sessions.length} /> 个会话
  </span>
</h2>

// 应用广场标题
<h2 className="mb-4 text-base font-semibold text-foreground">
  应用广场
  <span className="ml-2 text-sm font-normal text-muted">
    共 <AnimatedNumber value={apps.length} /> 个网站
  </span>
</h2>

// 两个列表容器加呼吸类
<ul className={`space-y-2 ${sessionsBreathing ? "animate-breath" : ""}`}>
<div className={`grid gap-3 sm:grid-cols-2 ${appsBreathing ? "animate-breath" : ""}`}>
```

- [ ] **Step 2: AdminUsersPanel / AdminClientsPage 计数与呼吸**

```tsx
const usersBreathing = useBreathOnChange(users);

<h2 className="text-lg font-semibold text-foreground">
  用户管理
  <span className="ml-2 text-sm font-normal text-muted">
    共 <AnimatedNumber value={users.length} /> 个账号
  </span>
</h2>
<div className={`table-shell ${usersBreathing ? "animate-breath" : ""}`}>
```

```tsx
const clientsBreathing = useBreathOnChange(clients);

<h2 className="text-lg font-semibold text-foreground">
  授权网站管理
  <span className="ml-2 text-sm font-normal text-muted">
    共 <AnimatedNumber value={clients.length} /> 个应用
  </span>
</h2>
<ul className={`space-y-3 ${clientsBreathing ? "animate-breath" : ""}`}>
```

- [ ] **Step 3: AdminAuditPanel 刷新闭环**

```tsx
const logsBreathing = useBreathOnChange(logs);
const refreshAction = useAsyncAction(
  async () => {
    const next = await adminAuditApi.list();
    setLogs(next);
  },
  { onError: (err) => toast.error(err instanceof Error ? err.message : "刷新失败") },
);

<AsyncButton type="button" status={refreshAction.status} onClick={() => void refreshAction.run()}>
  刷新
</AsyncButton>
<div className={`table-shell ${logsBreathing ? "animate-breath" : ""}`}>
```

审计列表头部计数：

```tsx
共 <AnimatedNumber value={logs.length} /> 条记录
```

- [ ] **Step 4: 运行全部前端测试**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/pages/AdminUsersPanel.tsx frontend/src/pages/AdminClientsPage.tsx frontend/src/pages/AdminAuditPanel.tsx
git commit -m "feat: 数字滚动计数与数据刷新呼吸动画"
```

---

### Task 10: 全量验证与文档同步

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-motion-feedback-loop-design.md`（状态改为“已实施完成”）

- [ ] **Step 1: 全量构建**

Run: `npx tsc -b && npm run lint && npm run build`
Expected: 全部通过

- [ ] **Step 2: 人工走查清单**

- 登录失败：按钮恢复可点击 + Toast 报错
- 登录成功：按钮短暂显示“已完成”后跳转
- 快速连点任意异步按钮：只发起一次请求
- 后台批量操作：按钮 pending → 表格呼吸 + 计数滚动
- 明暗两态下按钮波纹、spinner、成功色可读
- `prefers-reduced-motion: reduce` 下无波纹、数字直接到位

- [ ] **Step 3: 更新 spec 状态**

把 `- 状态：待用户评审` 改为 `- 状态：已实施完成（2026-08-13）`。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/specs/2026-08-13-motion-feedback-loop-design.md
git commit -m "docs: 交互动效与请求反馈闭环实施完成"
```

---

## Self-Review

- Spec 覆盖：按钮波纹（Task 1）、Toast 增强（Task 2）、请求状态机与 AsyncButton（Task 3）、数字滚动/呼吸 Hook（Task 4）、认证页/授权页（Task 5）、用户中心（Task 6）、后台用户（Task 7）、后台应用/设置（Task 8）、计数与呼吸接入（Task 9）、验证与文档（Task 10）。
- 类型一致性：`AsyncStatus` 统一由 `useAsyncAction.ts` 导出；`ConfirmDialog` 新增 `status?: AsyncStatus`；所有页面按钮使用同一 `status` prop。
- 无占位：每个任务都给出可运行代码与验证命令；行内操作统一用共享 action + `pending` 计算，避免 hooks 循环调用。
