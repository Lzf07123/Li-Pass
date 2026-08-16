import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuestOnly } from "../components/GuestOnly";

function renderGuestOnly(entry = "/login") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route
          path="/login"
          element={
            <GuestOnly>
              <div>登录表单</div>
            </GuestOnly>
          }
        />
        <Route path="/" element={<div>用户中心</div>} />
        <Route path="/oauth2/authorize" element={<div>授权页</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("GuestOnly", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("未登录时正常渲染登录表单", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "未登录" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    renderGuestOnly();
    await waitFor(() => expect(screen.getByText("登录表单")).toBeInTheDocument());
  });

  it("已登录访问 /login 时跳回用户中心", async () => {
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
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    renderGuestOnly();
    await waitFor(() => expect(screen.getByText("用户中心")).toBeInTheDocument());
    expect(screen.queryByText("登录表单")).not.toBeInTheDocument();
  });

  it("已登录访问带 next 的 /login 时跳转到安全 next", async () => {
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
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    renderGuestOnly("/login?next=/oauth2/authorize");
    await waitFor(() => expect(screen.getByText("授权页")).toBeInTheDocument());
  });

  it("已登录访问带绝对同源 next 的 /login 时用 location.replace 恢复授权", async () => {
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
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    const original = window.location;
    const replace = vi.fn();
    Object.defineProperty(window, "location", {
      value: { href: "", origin: "http://localhost", replace },
      writable: true,
      configurable: true,
    });
    const target = "http://localhost/oauth2/authorize?code_challenge=x";
    renderGuestOnly(`/login?next=${encodeURIComponent(target)}`);
    await waitFor(() => expect(replace).toHaveBeenCalledWith(target));
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });
});
