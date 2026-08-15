import { fireEvent, screen, waitFor } from "@testing-library/react";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

import { RegisterPage } from "../pages/RegisterPage";
import { ToastProvider } from "../components/ToastProvider";

function LoginProbe() {
  const location = useLocation();
  return <div>{`login${location.search}`}</div>;
}

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("提交注册请求并跳转到登录页", async () => {
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

    render(
      <MemoryRouter initialEntries={["/register"]}>
        <ToastProvider>
          <Routes>
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/login" element={<div>登录页占位</div>} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

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
    await waitFor(() =>
      expect(screen.getByText("登录页占位")).toBeInTheDocument()
    );
  });

  it("注册成功跳转登录页时保留 next 回跳参数", async () => {
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

    render(
      <MemoryRouter initialEntries={["/register?next=%2Foauth2%2Fauthorize"]}>
        <ToastProvider>
          <Routes>
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/login" element={<LoginProbe />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    await screen.findByLabelText("邮箱");
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("昵称"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "注册" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          "login?email=a%40example.com&next=%2Foauth2%2Fauthorize",
        ),
      ).toBeInTheDocument()
    );
  });
});
