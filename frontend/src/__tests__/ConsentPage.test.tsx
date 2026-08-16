import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsentPage } from "../pages/ConsentPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConsentPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("同意后跳转到 redirect_url", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "r1",
            client: { name: "Demo", logo_url: null, description: "" },
            scopes: ["openid", "profile"],
            user: { email: "a@example.com", nickname: "Alice" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ redirect_url: "http://localhost:3001/callback?code=abc" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });

    renderWithProviders(<ConsentPage />, ["/consent?request_id=r1"]);
    await waitFor(() => expect(screen.getAllByText("Demo").length).toBeGreaterThan(0));
    expect(screen.getByText("OpenID 身份标识")).toBeInTheDocument();
    expect(screen.getByText("昵称与头像等基本资料")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "同意授权" }));
    await waitFor(() =>
      expect(window.location.href).toBe("http://localhost:3001/callback?code=abc")
    );
    Object.defineProperty(window, "location", { value: original, configurable: true });
  });

  it("展示当前登录身份并可切换账号", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "r1",
            client: { name: "Demo", logo_url: null, description: "" },
            scopes: ["openid"],
            user: { email: "a@example.com", nickname: "Alice" },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ message: "已退出当前账号" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    vi.stubGlobal("fetch", fetchMock);
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });

    renderWithProviders(<ConsentPage />, ["/consent?request_id=r1"]);
    await waitFor(() =>
      expect(screen.getByText("a@example.com")).toBeInTheDocument()
    );
    fireEvent.click(
      screen.getByRole("button", { name: "使用其他账号登录" })
    );
    await waitFor(() =>
      expect(window.location.href).toBe(
        "/login?next=%2Fconsent%3Frequest_id%3Dr1"
      )
    );
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });
});
