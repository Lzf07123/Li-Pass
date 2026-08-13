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
        new Response(JSON.stringify({ logout_uri: "http://localhost:3001/logout" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
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

  it("管理员可见管理后台入口", async () => {
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
});
