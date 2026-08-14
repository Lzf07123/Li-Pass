import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LineChart } from "../components/charts/LineChart";

describe("LineChart", () => {
  it("渲染 aria-label、图例与屏幕阅读器数据表", () => {
    render(
      <LineChart
        labels={["07-16", "07-17"]}
        series={[
          { name: "登录次数", values: [12, 8] },
          { name: "登录人数", values: [9, 6], dashed: true },
        ]}
        formatValue={(value) => `${value} 次`}
      />,
    );

    const chart = screen.getByRole("img");
    expect(chart).toHaveAttribute(
      "aria-label",
      "登录次数、登录人数 最近 2 天趋势图",
    );

    // 图例与屏幕阅读器表头都会出现系列名。
    expect(screen.getAllByText("登录次数").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("登录人数").length).toBeGreaterThanOrEqual(2);

    const table = screen.getByRole("table");
    expect(table).toHaveTextContent("07-16");
    expect(table).toHaveTextContent("07-17");
    expect(table).toHaveTextContent("12 次");
    expect(table).toHaveTextContent("6 次");
  });

  it("图例文字禁止换行", () => {
    render(
      <LineChart
        labels={["07-16"]}
        series={[
          { name: "登录次数", values: [12] },
          { name: "新增注册", values: [3], dashed: true },
        ]}
      />,
    );

    const legendItems = screen
      .getAllByText(/登录次数|新增注册/)
      .filter((node) => node.tagName === "SPAN");
    expect(legendItems.length).toBeGreaterThanOrEqual(2);
    for (const item of legendItems) {
      expect(item.className).toContain("whitespace-nowrap");
    }
    const container = legendItems[0].parentElement;
    expect(container?.className).toContain("overflow-x-auto");
  });
});
