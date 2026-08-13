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
