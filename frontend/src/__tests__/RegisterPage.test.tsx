import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterPage } from "../pages/RegisterPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("提交注册请求并跳转到验证页", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/auth/register/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ public_registration_enabled: true }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: false,
            role: "user",
            status: "active",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } }
        )
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<RegisterPage />);

    await screen.findByLabelText("邮箱");
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("昵称"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "注册" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const registerCall = fetchMock.mock.calls.find(
      (call) =>
        String(call[0]).includes("/api/v1/auth/register") &&
        (call[1] as RequestInit | undefined)?.method === "POST"
    );
    const url = String(registerCall?.[0]);
    const init = registerCall?.[1] as RequestInit | undefined;
    expect(url).toContain("/api/v1/auth/register");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      email: "a@example.com",
      nickname: "Alice",
      password: "password123",
    });
  });
});
