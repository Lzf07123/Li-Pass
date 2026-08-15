import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LogoutConfirmPage } from "../pages/LogoutConfirmPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("LogoutConfirmPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("确认退出后跳转到回跳地址", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "确认退出" }));
    await waitFor(() =>
      expect(window.location.href).toBe("https://x.example/after?state=st-1")
    );
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });

  it("取消后跳回回跳地址且不触发确认接口", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() =>
      expect(window.location.href).toBe("https://x.example/after")
    );
    const confirmCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes("/confirm")
    );
    expect(confirmCall).toBeUndefined();
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
});
