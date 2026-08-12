import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("登录失败时展示错误信息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "邮箱或密码错误" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

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
    render(
      <MemoryRouter initialEntries={["/login?next=/oauth2/authorize"]}>
        <LoginPage />
      </MemoryRouter>
    );
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "验证" })).toBeInTheDocument()
    );
  });
});
