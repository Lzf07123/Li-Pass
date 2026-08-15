import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";
import { isSafeNext } from "../lib/navigation";
import { renderWithProviders } from "../test/renderWithProviders";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("从注册跳转携带的邮箱参数预填账号", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    renderWithProviders(<LoginPage />, ["/login?email=a@example.com"]);
    expect(screen.getByLabelText("邮箱")).toHaveValue("a@example.com");
  });

  it("从 localStorage 回填记住的账号与密码", () => {
    window.localStorage.setItem("lipass.remember.account", "a@example.com");
    window.localStorage.setItem("lipass.remember.password", "password123");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));

    renderWithProviders(<LoginPage />);

    expect(screen.getByLabelText("邮箱")).toHaveValue("a@example.com");
    expect(screen.getByLabelText("密码")).toHaveValue("password123");
    expect(screen.getByLabelText("记住账号")).toBeChecked();
    expect(screen.getByLabelText("记住密码")).toBeChecked();
  });

  it("登录成功后按勾选落盘记住的凭据", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
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
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByLabelText("记住账号"));
    fireEvent.click(screen.getByLabelText("记住密码"));
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() =>
      expect(
        window.localStorage.getItem("lipass.remember.account"),
      ).toBe("a@example.com")
    );
    expect(
      window.localStorage.getItem("lipass.remember.password"),
    ).toBe("password123");
  });

  it("登录失败不落盘记住的凭据", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "邮箱或密码错误" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText("密码"), {
      target: { value: "wrongpass" },
    });
    fireEvent.click(screen.getByLabelText("记住账号"));
    fireEvent.click(screen.getByLabelText("记住密码"));
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() =>
      expect(screen.getByText("邮箱或密码错误")).toBeInTheDocument()
    );
    expect(
      window.localStorage.getItem("lipass.remember.account"),
    ).toBeNull();
    expect(
      window.localStorage.getItem("lipass.remember.password"),
    ).toBeNull();
  });

  it("登录失败时展示错误信息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "邮箱或密码错误" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(screen.getByText("邮箱或密码错误")).toBeInTheDocument());
  });

  it("登录返回 requires_2fa 时进入验证码步骤", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requires_2fa: true,
          challenge_id: "ch-1",
          methods: ["email_otp", "recovery"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<LoginPage />, ["/login?next=/oauth2/authorize"]);
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "验证" })).toBeInTheDocument()
    );
  });

  it("next 白名单：仅允许同源或 API 同源地址", () => {
    const origin = window.location.origin;
    expect(isSafeNext(`${origin}/oauth2/authorize`)).toBe(true);
    expect(isSafeNext("/oauth2/authorize?x=1")).toBe(true);
    expect(isSafeNext("https://evil.example")).toBe(false);
    expect(isSafeNext("//evil.example")).toBe(false);
    expect(isSafeNext("javascript:alert(1)")).toBe(false);
  });

  it("next 参数不安全时展示告警，登录后停留个人中心", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    renderWithProviders(<LoginPage />, [
      "/login?next=https%3A%2F%2Fevil.example%2Foauth2%2Fauthorize",
    ]);
    expect(
      screen.getByText(
        "无法验证返回原网站的链接（域名或协议与门户不一致），登录完成后将停留在门户个人中心。",
      ),
    ).toBeInTheDocument();
  });

  it("注册链接透传 next 参数以保留应用回跳", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    renderWithProviders(<LoginPage />, [
      "/login?next=%2Foauth2%2Fauthorize",
    ]);
    expect(screen.getByRole("link", { name: "注册新账号" })).toHaveAttribute(
      "href",
      "/register?next=%2Foauth2%2Fauthorize",
    );
  });
});
