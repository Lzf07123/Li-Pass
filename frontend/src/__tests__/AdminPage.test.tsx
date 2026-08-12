import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminPage } from "../pages/AdminPage";

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
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("bob@example.com")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "审计日志" }));
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
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("无权访问管理后台")).toBeInTheDocument());
  });
});
