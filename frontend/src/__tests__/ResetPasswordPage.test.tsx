import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResetPasswordPage } from "../pages/ResetPasswordPage";

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("成功重置密码后展示成功消息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "密码已重置" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/reset-password?email=a%40example.com"]}>
        <ResetPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText("验证码"), { target: { value: "123456" } });
    fireEvent.change(screen.getByLabelText("新密码"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText("确认新密码"), {
      target: { value: "newpassword123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

    await waitFor(() =>
      expect(screen.getByText(/密码已重置/)).toBeInTheDocument()
    );
    const call = fetchMock.mock.calls[0];
    expect(String(call?.[0])).toContain("/api/v1/auth/password/reset/confirm");
    expect(JSON.parse(String((call?.[1] as RequestInit | undefined)?.body))).toEqual({
      email: "a@example.com",
      code: "123456",
      new_password: "newpassword123",
    });
    expect(screen.getByRole("link", { name: "去登录" })).toBeInTheDocument();
  });

  it("两次密码不一致时提示错误", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("邮箱"), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText("验证码"), { target: { value: "123456" } });
    fireEvent.change(screen.getByLabelText("新密码"), {
      target: { value: "newpassword123" },
    });
    fireEvent.change(screen.getByLabelText("确认新密码"), {
      target: { value: "different456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

    await waitFor(() =>
      expect(screen.getByText("两次输入的新密码不一致")).toBeInTheDocument()
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
