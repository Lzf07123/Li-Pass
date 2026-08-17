import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LegalPage } from "../pages/LegalPage";

function renderPage(kind: "privacy" | "terms") {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
  );
  return render(
    <MemoryRouter>
      <LegalPage kind={kind} />
    </MemoryRouter>
  );
}

describe("LegalPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染隐私政策关键章节与联系入口", () => {
    renderPage("privacy");
    expect(
      screen.getByRole("heading", { name: "隐私政策" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "我们收集的信息" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "你的权利" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "18312052639@163.com" })
    ).toHaveAttribute("href", "mailto:18312052639@163.com");
    expect(
      screen.getByRole("link", { name: "GitHub Issues" })
    ).toHaveAttribute("href", "https://github.com/Lzf07123/Li-Pass/issues");
    expect(screen.getByRole("link", { name: "服务条款" })).toBeInTheDocument();
  });

  it("渲染服务条款关键章节与联系入口", () => {
    renderPage("terms");
    expect(
      screen.getByRole("heading", { name: "服务条款" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "账号与安全责任" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "法律适用与争议" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "18312052639@163.com" })
    ).toHaveAttribute("href", "mailto:18312052639@163.com");
    expect(
      screen.getByRole("link", { name: "Apache-2.0" })
    ).toHaveAttribute(
      "href",
      "https://github.com/Lzf07123/Li-Pass/blob/main/LICENSE"
    );
  });
});
