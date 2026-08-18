import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminPage } from "../pages/AdminPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("AdminPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("管理员可查看用户管理并切换审计日志", async () => {
    const fetchMock = vi
      .fn()
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
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "2",
              email: "bob@example.com",
              nickname: "Bob",
              phone: null,
              email_verified: true,
              role: "user",
              status: "active",
              created_at: "2026-08-12T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "a1",
              actor_type: "user",
              actor_id: "2",
              action: "login",
              target_type: null,
              target_id: null,
              ip: "127.0.0.1",
              detail: null,
              created_at: "2026-08-12T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminPage />, ["/admin/users"]);
    await waitFor(() => expect(screen.getByText("bob@example.com")).toBeInTheDocument());
    const bobEmail = screen.getByText("bob@example.com");
    expect(bobEmail).toHaveClass("table-cell-clip");
    expect(bobEmail).toHaveAttribute("title", "bob@example.com");
    expect(screen.getByText("邮箱").closest("th")).toHaveClass(
      "whitespace-nowrap"
    );
    fireEvent.click(screen.getByRole("link", { name: "审计日志" }));
    await waitFor(() => expect(screen.getByText("login")).toBeInTheDocument());
  });

  it("普通用户访问管理后台显示无权访问", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "1",
            email: "u@example.com",
            nickname: "U",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    renderWithProviders(<AdminPage />, ["/admin/users"]);
    await waitFor(() => expect(screen.getByText("无权访问管理后台")).toBeInTheDocument());
  });

  it("重置密码通过内联表单提交", async () => {
    const fetchMock = vi
      .fn()
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
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "2",
              email: "bob@example.com",
              nickname: "Bob",
              phone: null,
              email_verified: true,
              role: "user",
              status: "active",
              created_at: "2026-08-12T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: false,
            window_minutes: 30,
            expires_in_seconds: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ message: "密码已重置，该用户所有会话已退出" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminPage />, ["/admin/users"]);
    await waitFor(() => expect(screen.getByText("bob@example.com")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "重置密码" }));
    fireEvent.change(screen.getByLabelText("管理员当前密码"), {
      target: { value: "adminpass" },
    });
    const input = await screen.findByPlaceholderText("至少 8 位");
    fireEvent.change(input, { target: { value: "newpassword456" } });
    fireEvent.click(screen.getByRole("button", { name: "确认重置" }));
    await waitFor(() =>
      expect(screen.getByText("密码已重置，该用户所有会话已退出")).toBeInTheDocument()
    );
    const resetCall = fetchMock.mock.calls.find(
      (call) => String(call[0]).includes("/reset-password")
    );
    expect(String(resetCall?.[0])).toContain("/api/v1/admin/users/2/reset-password");
    expect(JSON.parse(String((resetCall?.[1] as RequestInit | undefined)?.body))).toEqual({
      new_password: "newpassword456",
      current_password: "adminpass",
    });
  });

  it("自己的禁用按钮不可用", async () => {
    const fetchMock = vi
      .fn()
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
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "1",
              email: "admin@example.com",
              nickname: "Admin",
              phone: null,
              email_verified: true,
              role: "admin",
              status: "active",
              created_at: "2026-08-12T00:00:00Z",
            },
            {
              id: "2",
              email: "bob@example.com",
              nickname: "Bob",
              phone: null,
              email_verified: true,
              role: "user",
              status: "active",
              created_at: "2026-08-12T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminPage />, ["/admin/users"]);
    await waitFor(() => expect(screen.getByText("admin@example.com")).toBeInTheDocument());
    const adminRow = screen.getByText("admin@example.com").closest("tr");
    expect(adminRow).not.toBeNull();
    expect(
      within(adminRow as HTMLElement).getByRole("button", { name: "禁用" })
    ).toBeDisabled();
  });
});
