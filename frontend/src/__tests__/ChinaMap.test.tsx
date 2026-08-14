import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChinaMap } from "../components/charts/ChinaMap";

describe("ChinaMap", () => {
  it("渲染省份着色、徽章与明细表", () => {
    render(
      <ChinaMap
        data={[
          { name: "广东省", value: 12 },
          { name: "北京市", value: 6 },
        ]}
        others={{ overseas: 4, internal: 2, unknown: 1 }}
      />,
    );

    expect(
      screen.getByRole("img", { name: /中国登录来源地域分布图/ }),
    ).toBeInTheDocument();

    const guangdong = document.querySelector('[data-name="广东省"]');
    expect(guangdong).not.toBeNull();
    expect(guangdong?.getAttribute("d")).not.toContain("NaN");
    expect(Number(guangdong?.getAttribute("fill-opacity"))).toBeGreaterThan(0);
    const beijing = document.querySelector('[data-name="北京市"]');
    expect(Number(beijing?.getAttribute("fill-opacity"))).toBeGreaterThan(0);
    const shanghai = document.querySelector('[data-name="上海市"]');
    expect(shanghai?.getAttribute("data-value")).toBe("0");

    expect(screen.getByText("海外 4")).toBeInTheDocument();
    expect(screen.getByText("内网 2")).toBeInTheDocument();
    expect(screen.getByText("其它 1")).toBeInTheDocument();

    const table = screen.getByRole("table");
    expect(table).toHaveTextContent("广东省");
    expect(table).toHaveTextContent("12");
    expect(table).toHaveTextContent("北京市");
  });

  it("悬停省份显示次数与占比提示", () => {
    render(
      <ChinaMap
        data={[{ name: "广东省", value: 12 }]}
        others={{ overseas: 0, internal: 0, unknown: 0 }}
      />,
    );

    const guangdong = document.querySelector(
      '[data-name="广东省"]',
    ) as SVGPathElement;
    fireEvent.mouseEnter(guangdong);
    expect(screen.getByText("广东省 · 12 次 · 100.0%")).toBeInTheDocument();
    fireEvent.mouseLeave(guangdong);
    expect(
      screen.queryByText("广东省 · 12 次 · 100.0%"),
    ).not.toBeInTheDocument();
  });

  it("无省份数据时隐藏色阶图例，仅保留徽章与空明细表", () => {
    render(
      <ChinaMap
        data={[]}
        others={{ overseas: 3, internal: 0, unknown: 0 }}
      />,
    );

    expect(screen.getByText("海外 3")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.queryByText(/–/)).not.toBeInTheDocument();
    const map = screen.getByRole("img", {
      name: /中国登录来源地域分布图/,
    });
    expect(
      map.querySelectorAll('path[fill-opacity]:not([fill-opacity="0"])'),
    ).toHaveLength(0);
  });
});
