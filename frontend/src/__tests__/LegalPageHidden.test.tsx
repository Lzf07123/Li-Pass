import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/brand", () => ({
  APP_NAME: "Li&Pass",
  APP_LOGO: "/brand-logo.webp",
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

import { LegalPage } from "../pages/LegalPage";

describe("LegalPage（联系变量置空）", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    );
  });

  it("隐藏邮箱与 GitHub Issues 链接，页脚附加链接同步隐藏", () => {
    render(
      <MemoryRouter>
        <LegalPage kind="privacy" />
      </MemoryRouter>
    );
    expect(
      screen.queryByRole("link", { name: "18312052639@163.com" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "GitHub Issues" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "隐私政策" })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "联系我们" })
    ).toBeInTheDocument();
  });
});
