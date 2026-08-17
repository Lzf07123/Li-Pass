import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { SiteFooter } from "../components/SiteFooter";

function renderFooter() {
  return render(
    <MemoryRouter>
      <SiteFooter />
    </MemoryRouter>
  );
}

describe("SiteFooter（未配置备案信息）", () => {
  it("不显示占位备案链接", () => {
    renderFooter();
    expect(
      screen.queryByRole("link", { name: /ICP备/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /公网安备/ }),
    ).not.toBeInTheDocument();
  });

  it("默认展示隐私政策与服务条款内部链接", () => {
    renderFooter();
    expect(screen.getByRole("link", { name: "隐私政策" })).toHaveAttribute(
      "href",
      "/privacy"
    );
    expect(screen.getByRole("link", { name: "服务条款" })).toHaveAttribute(
      "href",
      "/terms"
    );
  });

  it("展示 GitHub、反馈问题与联系我们", () => {
    renderFooter();
    const github = screen.getByRole("link", { name: "GitHub" });
    expect(github).toHaveAttribute(
      "href",
      "https://github.com/Lzf07123/Li-Pass"
    );
    expect(github).toHaveAttribute("target", "_blank");
    expect(github).toHaveAttribute("rel", "noreferrer");
    expect(
      screen.getByRole("link", { name: "反馈问题" })
    ).toHaveAttribute(
      "href",
      "https://github.com/Lzf07123/Li-Pass/issues"
    );
    expect(screen.getByRole("link", { name: "联系我们" })).toHaveAttribute(
      "href",
      "mailto:18312052639@163.com"
    );
  });

  it("展示开源协议链接", () => {
    renderFooter();
    const license = screen.getByRole("link", {
      name: "开源协议（Apache-2.0）",
    });
    expect(license).toHaveAttribute(
      "href",
      "https://github.com/Lzf07123/Li-Pass/blob/main/LICENSE"
    );
    expect(license).toHaveAttribute("target", "_blank");
    expect(license).toHaveAttribute("rel", "noreferrer");
  });

});
