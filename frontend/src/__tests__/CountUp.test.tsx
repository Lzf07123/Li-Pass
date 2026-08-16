import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CountUp } from "../components/bits/CountUp";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CountUp", () => {
  it("prefers-reduced-motion 时直接显示目标值", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn() }),
    );
    render(<CountUp from={0} to={42} />);

    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("渲染计数容器 span", () => {
    const { container } = render(<CountUp from={0} to={100} />);

    expect(container.querySelector("span")).not.toBeNull();
  });

  it("向下计数时最终显示 from 值", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn() }),
    );
    render(<CountUp from={5} to={0} direction="down" />);

    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
