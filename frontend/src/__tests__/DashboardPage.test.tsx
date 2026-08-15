import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../pages/DashboardPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染用户信息与应用广场", async () => {
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
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              client_id: "cli_demo",
              name: "Demo",
              description: "",
              logo_url: null,
              home_url: "http://localhost:3001",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
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
    await waitFor(() => expect(screen.getByDisplayValue("Alice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "上传头像" })).toBeInTheDocument();
  });

  it("退出所有设备保留当前会话并刷新列表", async () => {
    const current = {
      id: "s1",
      device_name: "MacBook Pro",
      ip: "127.0.0.1",
      user_agent: "ua",
      created_at: "2026-08-15T00:00:00Z",
      last_used_at: "2026-08-15T01:00:00Z",
      expires_at: "2026-09-15T00:00:00Z",
      current: true,
    };
    const other = { ...current, id: "s2", device_name: "iPhone", current: false };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), { status: 200 })
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([current, other]), { status: 200 })
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ revoked: 1 }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([current]), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), { status: 200 })
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);

    await waitFor(() => expect(screen.getByText("iPhone")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "退出所有设备" }));
    expect(
      screen.getByText(/确定退出除当前设备外的 1 台设备吗/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "全部退出" }));

    await waitFor(() =>
      expect(screen.getByText(/已退出 1 台设备/)).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.queryByText("iPhone")).not.toBeInTheDocument(),
    );
    const revokeCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).endsWith("/api/v1/sessions/revoke-all"),
    );
    expect((revokeCall?.[1] as RequestInit | undefined)?.method).toBe("POST");
  });

  it("仅剩当前设备时退出所有设备按钮不可用", async () => {
    const current = {
      id: "s1",
      device_name: "MacBook Pro",
      ip: "127.0.0.1",
      user_agent: "ua",
      created_at: "2026-08-15T00:00:00Z",
      last_used_at: "2026-08-15T01:00:00Z",
      expires_at: "2026-09-15T00:00:00Z",
      current: true,
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ unread: 0 }), { status: 200 })
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
            { status: 200 }
          )
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify([]), { status: 200 })
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify([current]), { status: 200 })
        )
        .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
.mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              email_otp_enabled: false,
              totp_enabled: false,
              recovery_codes_remaining: 0,
            }),
            { status: 200 }
          )
        )
    );
    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("MacBook Pro")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "退出所有设备" })).toBeDisabled();
  });

  it("取消授权后应用从广场移除", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });
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
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              client_id: "cli_demo",
              name: "Demo",
              description: "",
              logo_url: null,
              home_url: "http://localhost:3001",
            },
          ]),
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            logout_uri: "http://localhost:3001/logout",
            backchannel_notified: false,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "取消授权" }));
    fireEvent.click(screen.getByRole("button", { name: "确认取消" }));
    await waitFor(() => expect(screen.queryByText("Demo")).not.toBeInTheDocument());
    const deleteCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "DELETE"
    );
    expect(String(deleteCall?.[0])).toContain("/api/v1/apps/cli_demo");
    await waitFor(() =>
      expect(window.location.href).toContain("http://localhost:3001/logout?next=")
    );
    Object.defineProperty(window, "location", { value: originalLocation, configurable: true });
  });

  it("仅回程登出的网站取消授权后提示已通知退出", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "", origin: "http://localhost" },
      writable: true,
      configurable: true,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), { status: 200 })
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              client_id: "cli_demo",
              name: "Demo",
              description: "",
              logo_url: null,
              home_url: "http://localhost:3001",
            },
          ]),
          { status: 200 }
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            logout_uri: null,
            backchannel_notified: true,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "取消授权" }));
    fireEvent.click(screen.getByRole("button", { name: "确认取消" }));
    await waitFor(() =>
      expect(
        screen.getByText("已取消对“Demo”的授权，已通知该网站退出登录"),
      ).toBeInTheDocument()
    );
    expect(window.location.href).toBe("");
    Object.defineProperty(window, "location", {
      value: originalLocation,
      configurable: true,
    });
  });

  it("未配置登出通道的网站取消授权后给出警告", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "", origin: "http://localhost" },
      writable: true,
      configurable: true,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), { status: 200 })
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              client_id: "cli_demo",
              name: "Demo",
              description: "",
              logo_url: null,
              home_url: "http://localhost:3001",
            },
          ]),
          { status: 200 }
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            logout_uri: null,
            backchannel_notified: false,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "取消授权" }));
    fireEvent.click(screen.getByRole("button", { name: "确认取消" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "已取消对“Demo”的授权，但该网站未配置登出通道，门户无法通知其下线；如仍显示已登录请在该网站手动退出",
        ),
      ).toBeInTheDocument()
    );
    expect(window.location.href).toBe("");
    Object.defineProperty(window, "location", {
      value: originalLocation,
      configurable: true,
    });
  });

  it("管理员可见管理后台入口", async () => {
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
            email: "admin@example.com",
            nickname: "Admin",
            email_verified: true,
            phone: null,
            role: "admin",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "管理后台" })).toBeInTheDocument()
    );
  });

  it("修改密码失败时在当前密码旁内联展示错误", async () => {
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
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "当前密码错误" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        })
      );
    vi.stubGlobal("fetch", fetchMock);
    const { container } = renderWithProviders(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByPlaceholderText("当前密码")).toBeInTheDocument()
    );

    fireEvent.change(screen.getByPlaceholderText("当前密码"), {
      target: { value: "wrongpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("新密码（至少 8 位）"), {
      target: { value: "newpassword123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "修改密码" }));

    await waitFor(() => {
      const inlineError = container.querySelector("#change-password-error");
      expect(inlineError).toBeTruthy();
      expect(inlineError).toHaveTextContent("当前密码错误");
    });
    expect(screen.getByPlaceholderText("当前密码")).toHaveAttribute(
      "aria-invalid",
      "true"
    );
  });

  it("保存资料时提交邮件通知开关", async () => {
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
            email_notifications: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
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
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            email_notifications: false,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(
        screen.getByRole("checkbox", { name: "接收邮件通知" })
      ).toBeChecked()
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "接收邮件通知" }));
    fireEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      const put = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).endsWith("/api/v1/me") && init?.method === "PUT"
      );
      expect(put).toBeDefined();
      const body = JSON.parse(
        String((put as [unknown, RequestInit])[1].body)
      );
      expect(body.email_notifications).toBe(false);
    });
  });

  it("展示可信设备并可移除", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), { status: 200 })
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
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "t1",
              device_name: "MacBook Pro",
              user_agent: "ua",
              ip: "127.0.0.1",
              created_at: "2026-08-15T00:00:00Z",
              expires_at: "2026-08-22T00:00:00Z",
              last_used_at: null,
              current: true,
            },
          ]),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200 }
        )
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText("可信设备")).toBeInTheDocument()
    );
    expect(screen.getByText("MacBook Pro")).toBeInTheDocument();
    expect(screen.getByText("当前")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "移除" }));
    await waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(
        (call) =>
          (call[1] as RequestInit | undefined)?.method === "DELETE" &&
          String(call[0]).includes("/api/v1/me/trusted-devices/t1"),
      );
      expect(deleteCall).toBeDefined();
    });
    await waitFor(() =>
      expect(screen.getByText("已移除该可信设备")).toBeInTheDocument()
    );
  });
});
