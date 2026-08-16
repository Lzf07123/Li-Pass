import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TechAmbience } from "../components/bits/TechAmbience";

describe("TechAmbience", () => {
  it("渲染科技网格、两条光束与呼吸光点", () => {
    const { container } = render(<TechAmbience />);

    expect(container.querySelector(".tech-grid")).toBeInTheDocument();
    expect(container.querySelectorAll(".tech-beam")).toHaveLength(2);
    expect(container.querySelectorAll(".tech-dot").length).toBeGreaterThanOrEqual(
      5,
    );
  });

  it("soft 模式在根节点标记并降低浓度", () => {
    const { container } = render(<TechAmbience soft />);

    expect(container.firstChild).toHaveClass("tech-ambience--soft");
  });

  it("装饰层对辅助技术不可见", () => {
    const { container } = render(<TechAmbience />);

    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });
});
