import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FloatingBackground } from "../components/FloatingBackground";

/** 记录绘制调用的 2D 上下文替身：jsdom 不实现 Canvas，用桩对象验证绘制行为 */
class MockContext {
  calls: string[] = [];
  moveToArgs: number[][] = [];
  fillStyle = "";
  strokeStyle = "";
  lineWidth = 1;
  globalAlpha = 1;

  setTransform() {
    this.calls.push("setTransform");
  }
  clearRect() {
    this.calls.push("clearRect");
  }
  fillRect() {
    this.calls.push("fillRect");
  }
  save() {
    this.calls.push("save");
  }
  restore() {
    this.calls.push("restore");
  }
  beginPath() {
    this.calls.push("beginPath");
  }
  moveTo(x: number, y: number) {
    this.calls.push("moveTo");
    this.moveToArgs.push([x, y]);
  }
  lineTo() {
    this.calls.push("lineTo");
  }
  rect() {
    this.calls.push("rect");
  }
  closePath() {
    this.calls.push("closePath");
  }
  fill() {
    this.calls.push("fill");
  }
  stroke() {
    this.calls.push("stroke");
  }
}

const contexts: MockContext[] = [];
const rafById = new Map<number, FrameRequestCallback>();
let rafNextId = 0;
let frameClock = 0;

function installEnvironment(mediaMatches: Record<string, boolean> = {}) {
  contexts.length = 0;
  rafById.clear();
  rafNextId = 0;
  frameClock = performance.now();

  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    function getContext(this: HTMLCanvasElement) {
      const context = new MockContext();
      contexts.push(context);
      return context as unknown as CanvasRenderingContext2D;
    },
  );

  // jsdom 中画布尺寸为 0，这里固定为 800×600，使绘制逻辑真正执行
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", {
    configurable: true,
    get: () => 800,
  });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", {
    configurable: true,
    get: () => 600,
  });

  // 受控 rAF：回调入队由测试手动推进，cancel 真正移除回调，便于验证卸载清理
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    rafNextId += 1;
    rafById.set(rafNextId, callback);
    return rafNextId;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => {
    rafById.delete(id);
  });

  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: mediaMatches[query] ?? false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

/** 手动推进 N 帧动画（每帧 16ms，与 60fps 基准一致） */
function advanceFrames(count: number, step = 16) {
  act(() => {
    for (let frameIndex = 0; frameIndex < count; frameIndex++) {
      const pending = [...rafById.values()];
      rafById.clear();
      frameClock += step;
      for (const callback of pending) {
        callback(frameClock);
      }
    }
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientWidth");
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientHeight");
  document.documentElement.classList.remove("dark");
});

describe("FloatingBackground", () => {
  it("渲染后绘制几何形状，并随动画循环持续推进", () => {
    installEnvironment();
    render(<FloatingBackground shapeCount={7} />);
    const context = contexts[0]!;

    // 挂载即完成首帧：默认不透明画布应清屏 + 填充背景 + 绘制 7 个形状
    expect(context.calls).toContain("clearRect");
    expect(context.calls).toContain("fillRect");
    expect(context.calls.filter((call) => call === "stroke")).toHaveLength(7);

    // 每推进一帧，7 个形状各描边一次
    advanceFrames(2);
    expect(context.calls.filter((call) => call === "stroke")).toHaveLength(21);
  });

  it("transparent 时只清屏，不绘制背景色", () => {
    installEnvironment();
    render(<FloatingBackground transparent shapeCount={3} />);
    const context = contexts[0]!;
    expect(context.calls).toContain("clearRect");
    expect(context.calls).not.toContain("fillRect");
  });

  it("theme=auto 时跟随 html.dark 类切换描边颜色", async () => {
    installEnvironment();
    document.documentElement.classList.remove("dark");
    render(<FloatingBackground theme="auto" transparent shapeCount={7} />);
    advanceFrames(1);
    const context = contexts[0]!;
    // 初始为浅色主题的深灰描边
    expect(context.strokeStyle).toBe("rgba(90, 105, 100, 0.5)");

    document.documentElement.classList.add("dark");
    // 等待 MutationObserver 回调，再推进约 480ms 让颜色过渡完成
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    advanceFrames(200); // 指数平滑收敛：约 3.2s 后通道值取整到目标
    expect(context.strokeStyle).toMatch(/^rgba\(196, 203, 208, /);
  });

  it("calm 聚焦减速：速度降至一半", () => {
    installEnvironment();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    render(<FloatingBackground transparent calm shapeCount={7} />);
    advanceFrames(1);
    const context = contexts[0]!;
    // 每帧 5 个 moveTo：3 个 Z 形各 1 个 + 2 个平行四边形各 1 个（正方形走 rect 无 moveTo）
    const frame1X = context.moveToArgs[5]![0]!;
    advanceFrames(1);
    const frame2X = context.moveToArgs[10]![0]!;
    // 远景层速度基准 0.175px/帧，calm 减半后约为 0.0875px/帧
    expect(Math.abs(frame2X - frame1X)).toBeCloseTo(0.0875, 2);
  });

  it("scrollWind 滚动风速：静止慢呼吸，滚动后提速", () => {
    installEnvironment();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    let scrollY = 0;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      get: () => scrollY,
    });
    render(<FloatingBackground transparent scrollWind shapeCount={7} />);
    advanceFrames(1);
    const context = contexts[0]!;
    const frame1X = context.moveToArgs[5]![0]!;

    // 一次快速滚动 30px，风速系数从 0.5 拉到约 1.4
    scrollY += 30;
    window.dispatchEvent(new Event("scroll"));
    advanceFrames(1);
    const frame2X = context.moveToArgs[10]![0]!;
    const delta = Math.abs(frame2X - frame1X);
    expect(delta).toBeGreaterThan(0.2);
    expect(delta).toBeLessThan(0.27);
  });

  it("移动端断点下形状数被限制到 6", () => {
    installEnvironment({ "(max-width: 767px)": true });
    render(<FloatingBackground shapeCount={10} />);
    expect(
      contexts[0]!.calls.filter((call) => call === "stroke"),
    ).toHaveLength(6);
  });

  it("系统要求减弱动效时只绘制静态帧，不启动动画循环", () => {
    installEnvironment({ "(prefers-reduced-motion: reduce)": true });
    render(<FloatingBackground shapeCount={5} />);
    expect(
      contexts[0]!.calls.filter((call) => call === "stroke"),
    ).toHaveLength(5);
    expect(rafById.size).toBe(0);
  });

  it("卸载时取消动画帧，不再继续绘制", () => {
    installEnvironment();
    const { unmount } = render(<FloatingBackground shapeCount={3} />);
    expect(rafById.size).toBe(1);
    unmount();
    expect(rafById.size).toBe(0);
    const strokeCount =
      contexts[0]!.calls.filter((call) => call === "stroke").length;
    advanceFrames(2);
    expect(
      contexts[0]!.calls.filter((call) => call === "stroke"),
    ).toHaveLength(strokeCount);
  });
});
