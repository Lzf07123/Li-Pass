import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScrollTabs } from "../components/ScrollTabs";

describe("ScrollTabs", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("渲染子标签并隐藏滚动条容器与边缘渐隐提示", () => {
    render(
      <ScrollTabs>
        <button type="button">用户管理</button>
        <button type="button">数据统计</button>
      </ScrollTabs>,
    );

    expect(screen.getByRole("button", { name: "用户管理" })).toBeInTheDocument();
    const scroller = screen.getByRole("button", { name: "用户管理" }).parentElement;
    expect(scroller).toHaveClass("scroll-tabs");
    const fades = document.querySelectorAll('[aria-hidden="true"]');
    expect(fades).toHaveLength(2);
    for (const fade of fades) {
      expect(fade).toHaveClass("pointer-events-none");
    }
  });

  it("活动标签变化时滚入视口中央", () => {
    const scrollSpy = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      value: scrollSpy,
      writable: true,
      configurable: true,
    });
    render(
      <ScrollTabs>
        <a href="#a">甲</a>
        <a href="#b" aria-current="page">
          乙
        </a>
      </ScrollTabs>,
    );

    expect(scrollSpy).toHaveBeenCalledWith(
      expect.objectContaining({ block: "nearest", inline: "center" }),
    );
  });
});
