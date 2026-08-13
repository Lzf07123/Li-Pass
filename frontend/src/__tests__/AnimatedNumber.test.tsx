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
