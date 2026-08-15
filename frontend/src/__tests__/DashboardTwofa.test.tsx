import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../pages/DashboardPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("DashboardPage 2FA", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染安全设置区", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("安全设置")).toBeInTheDocument());
  });

  it("step-up 窗口内关闭邮箱 2FA 无需再次输入密码", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: true,
            totp_enabled: true,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ message: "邮箱二次验证已关闭" }), {
          status: 200,
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: true,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("已开启（默认方案）")).toBeInTheDocument()
    );

    fireEvent.click(
      screen.getByRole("button", { name: "关闭邮箱二次验证" })
    );
    await waitFor(() => expect(screen.getByText("未开启")).toBeInTheDocument());

    const disableCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes("/api/v1/me/2fa/email/disable")
    );
    expect(disableCall).toBeTruthy();
    const body = JSON.parse(
      String((disableCall?.[1] as RequestInit | undefined)?.body),
    );
    expect(body.current_password).toBeUndefined();
  });

  it("窗口外关闭邮箱 2FA 要求输入密码", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: true,
            totp_enabled: true,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: false,
            window_minutes: 30,
            expires_in_seconds: 0,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("已开启（默认方案）")).toBeInTheDocument()
    );

    fireEvent.click(
      screen.getByRole("button", { name: "关闭邮箱二次验证" })
    );
    await waitFor(() =>
      expect(screen.getByText("请输入当前密码")).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("/api/v1/me/2fa/email/disable")
      ),
    ).toBe(false);
  });

  it("邮箱验证码为唯一方案时关闭按钮禁用并提示", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: true,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("已开启（默认方案）")).toBeInTheDocument()
    );
    expect(
      screen.getByRole("button", { name: "关闭邮箱二次验证" })
    ).toBeDisabled();
    expect(
      screen.getByText(/至少保留一种二次验证方式；如需关闭请先开启 TOTP 认证器/)
    ).toBeInTheDocument();
  });
});
