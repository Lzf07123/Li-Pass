import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/brand", () => ({
  APP_NAME: "Li&Pass",
  COPYRIGHT_HOLDER: "Li&Pass",
  FOOTER_LINKS: [],
  GITHUB_URL: "",
  GITHUB_ISSUES_URL: "",
  CONTACT_EMAIL: "",
  ICP_FILING_ICON: "/badges/icp.webp",
  ICP_FILING_TEXT: "",
  ICP_FILING_URL: "https://beian.miit.gov.cn/",
  POLICE_FILING_ICON: "/badges/police.webp",
  POLICE_FILING_TEXT: "",
  POLICE_FILING_URL: "https://beian.mps.gov.cn/",
}));

import { SiteFooter } from "../components/SiteFooter";

describe("SiteFooter（变量全部置空）", () => {
  it("隐藏 GitHub、反馈、联系与附加链接", () => {
    render(
      <MemoryRouter>
        <SiteFooter />
      </MemoryRouter>
    );
    expect(
      screen.queryByRole("link", { name: /GitHub/ })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "反馈问题" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "联系我们" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "隐私政策" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "服务条款" })
    ).not.toBeInTheDocument();
  });
});
