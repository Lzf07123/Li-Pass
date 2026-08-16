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

  it("批量启用只在被点击的按钮上显示处理中", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(usersResponse())
      .mockImplementationOnce(() => new Promise(() => {}));
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminUsersPanel currentAdminId="admin-1" />);

    await screen.findByText("alice@example.com");
    fireEvent.click(screen.getByLabelText("选择 alice@example.com"));
    fireEvent.click(screen.getByRole("button", { name: "批量启用" }));

    const pendingButton = await screen.findByRole("button", {
      name: "处理中…",
    });
    expect(pendingButton).toHaveAttribute("aria-busy", "true");

    const disableButton = screen.getByRole("button", { name: "批量禁用" });
    expect(disableButton).not.toHaveAttribute("aria-busy");
    expect(disableButton).toBeDisabled();
  });
});
