import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminUsersPanel } from "../pages/AdminUsersPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function usersResponse() {
  const body = [
    {
      id: "user-1",
      kind: "user",
      email: "alice@example.com",
      nickname: "Alice",
      phone: null,
      email_verified: true,
      role: "user",
      status: "active",
      created_at: "2026-08-01T00:00:00Z",
      expires_at: null,
    },
  ];
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminUsersPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("点击刷新按当前条件重新请求用户列表", async () => {
    const fetchMock = vi.fn().mockResolvedValue(usersResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminUsersPanel currentAdminId="admin-1" />);

    await screen.findByText("alice@example.com");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "/api/v1/admin/users",
    );
  });

  it("刷新失败时展示错误提示", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(usersResponse())
      .mockRejectedValueOnce(new Error("网络异常"));
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminUsersPanel currentAdminId="admin-1" />);

    await screen.findByText("alice@example.com");
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    await waitFor(() =>
      expect(screen.getByText("网络异常")).toBeInTheDocument()
    );
  });
});
