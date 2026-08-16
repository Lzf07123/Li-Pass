import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BlurText } from "../components/bits/BlurText";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BlurText", () => {
  it("按词拆分并渲染文本", () => {
    render(<BlurText text="一次注册 通行所有网站" animateBy="words" />);

    expect(screen.getByText(/一次注册/)).toBeInTheDocument();
    expect(screen.getByText(/通行所有网站/)).toBeInTheDocument();
  });

  it("prefers-reduced-motion 时静态渲染整段文本", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true }),
    );

    const { container } = render(<BlurText text="登录" animateBy="letters" />);

    expect(container.textContent).toBe("登录");
  });
});
