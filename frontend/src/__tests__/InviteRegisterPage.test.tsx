import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InviteRegisterPage } from "../pages/InviteRegisterPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("InviteRegisterPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("邀请链接有效时先校验通过再展示注册表单", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            valid: true,
            email: "i***@example.com",
            email_taken: false,
            expires_at: "2026-08-23T00:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithProviders(<InviteRegisterPage />, ["/invite?token=t1"]);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "完成注册" }),
      ).toBeInTheDocument()
    );
    expect(
      screen.getByText("邀请发送至 i***@example.com，设置密码即可激活账号"),
    ).toBeInTheDocument();
  });

  it("邀请链接过期时展示对应页面且不显示表单", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "邀请链接已过期，请联系管理员重新邀请" }),
          { status: 410, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithProviders(<InviteRegisterPage />, ["/invite?token=t1"]);
    await waitFor(() =>
      expect(
        screen.getByText("邀请链接已过期，请联系管理员重新邀请"),
      ).toBeInTheDocument()
    );
    expect(
      screen.queryByRole("button", { name: "完成注册" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "返回登录" }),
    ).toBeInTheDocument();
  });

  it("邀请邮箱已注册时提示直接登录", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            valid: true,
            email: "i***@example.com",
            email_taken: true,
            expires_at: "2026-08-23T00:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithProviders(<InviteRegisterPage />, ["/invite?token=t1"]);
    await waitFor(() =>
      expect(
        screen.getByText("邀请邮箱 i***@example.com 已注册账号，请直接登录。"),
      ).toBeInTheDocument()
    );
    expect(
      screen.queryByRole("button", { name: "完成注册" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去登录" })).toBeInTheDocument();
  });

  it("缺少 token 时提示邀请链接无效", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithProviders(<InviteRegisterPage />, ["/invite"]);
    expect(
      screen.getByText("邀请链接无效：缺少令牌参数。"),
    ).toBeInTheDocument();
  });
});
