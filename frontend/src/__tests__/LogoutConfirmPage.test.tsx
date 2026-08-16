import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LogoutConfirmPage } from "../pages/LogoutConfirmPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("LogoutConfirmPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("登出 SSO 后跳转到回跳地址", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ client_name: "Demo" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ redirect_url: "https://x.example/after?state=st-1" }),
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

    renderWithProviders(<LogoutConfirmPage />, ["/logout/confirm?request_id=r1"]);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "登出 SSO" }));
    await waitFor(() =>
      expect(window.location.href).toBe("https://x.example/after?state=st-1")
    );
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });

  it("仅登出本网站时保留门户会话且不触发确认接口", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ client_name: "Demo" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ redirect_url: "https://x.example/after" }), {
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

    renderWithProviders(<LogoutConfirmPage />, ["/logout/confirm?request_id=r1"]);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "仅登出本网站" }));
    await waitFor(() =>
      expect(window.location.href).toBe("https://x.example/after")
    );
    const confirmCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes("/confirm")
    );
    expect(confirmCall).toBeUndefined();
    const localOnlyCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes("/local-only")
    );
    expect(localOnlyCall).toBeDefined();
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });

  it("缺少 request_id 时提示错误而不是无限加载", async () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithProviders(<LogoutConfirmPage />, ["/logout/confirm"]);
    await waitFor(() =>
      expect(screen.getByText("缺少登出请求参数")).toBeInTheDocument()
    );
  });

  it("处理中状态只出现在被点击的按钮上", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ client_name: "Demo" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockImplementationOnce(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<LogoutConfirmPage />, [
      "/logout/confirm?request_id=r1",
    ]);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "登出 SSO" })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: "登出 SSO" }));
    const pendingButton = await screen.findByRole("button", {
      name: "处理中…",
    });
    expect(pendingButton).toHaveAttribute("aria-busy", "true");

    const localButton = screen.getByRole("button", { name: "仅登出本网站" });
    expect(localButton).not.toHaveAttribute("aria-busy");
    expect(localButton).toBeDisabled();
  });
});
