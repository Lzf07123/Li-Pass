import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../lib/brand", () => ({
  APP_NAME: "Li&Pass",
  COPYRIGHT_HOLDER: "Li&Pass",
  FOOTER_LINKS: [],
  GITHUB_URL: "",
  GITHUB_ISSUES_URL: "",
  CONTACT_EMAIL: "",
  LICENSE_NAME: "",
  LICENSE_URL: "",
  ICP_FILING_ICON: "/badges/icp.webp",
  ICP_FILING_TEXT: "京ICP备12345678号-1",
  ICP_FILING_URL: "https://beian.miit.gov.cn/",
  POLICE_FILING_ICON: "/badges/police.webp",
  POLICE_FILING_TEXT: "京公网安备 11000000000001号",
  POLICE_FILING_URL: "https://beian.mps.gov.cn/",
}));

import { SiteFooter } from "../components/SiteFooter";

describe("SiteFooter（已配置备案信息）", () => {
  it("显示备案与公安备案链接", () => {
    render(<SiteFooter />);
    expect(
      screen.getByRole("link", { name: /京ICP备12345678号-1/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /京公网安备 11000000000001号/ }),
    ).toBeInTheDocument();
  });
});
