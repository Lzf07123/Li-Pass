import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SiteFooter } from "../components/SiteFooter";

describe("SiteFooter（未配置备案信息）", () => {
  it("不显示占位备案链接", () => {
    render(<SiteFooter />);
    expect(
      screen.queryByRole("link", { name: /ICP备/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /公网安备/ }),
    ).not.toBeInTheDocument();
  });
});
