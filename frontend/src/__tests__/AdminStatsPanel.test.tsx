import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminStatsPanel } from "../pages/AdminStatsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function statsBody(overrides: Record<string, unknown> = {}) {
  const daily = Array.from({ length: 7 }, (_, index) => ({
    date: `2026-08-${String(8 + index).padStart(2, "0")}`,
    logins: 3 + index,
    login_users: 2 + index,
    registrations: index === 6 ? 1 : 0,
  }));
  return {
    generated_at: "2026-08-14T08:00:00Z",
    timezone: "Asia/Shanghai",
    days: 7,
    overview: {
      total_users: 128,
      active_users: 126,
      disabled_users: 2,
      admins: 3,
      verified_users: 120,
      online_sessions: 9,
      total_logins: 1024,
    },
    daily,
    auth_methods: [
      { method: "password", count: 7 },
      { method: "email_otp", count: 1 },
      { method: "totp", count: 1 },
      { method: "recovery", count: 0 },
    ],
    regions: [
      { region: "广东省 深圳市", count: 12 },
      { region: "United States", count: 4 },
      { region: "其它", count: 3 },
    ],
    ...overrides,
  };
}

function statsResponse(overrides: Record<string, unknown> = {}) {
  return new Response(JSON.stringify(statsBody(overrides)), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminStatsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染概览、图表图例与认证方式分布", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(statsResponse()));
    renderWithProviders(<AdminStatsPanel />);

    await waitFor(() => expect(screen.getByText("1,024")).toBeInTheDocument());
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("启用 126 · 禁用 2")).toBeInTheDocument();
    expect(screen.getByText("共 9 个在线会话")).toBeInTheDocument();
    expect(screen.getByText("密码")).toBeInTheDocument();
    expect(screen.getByText("邮箱验证码")).toBeInTheDocument();
    expect(screen.getByRole("img")).toBeInTheDocument();
    expect(screen.getAllByText("登录次数").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("新增注册").length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText(/登录来源地域分布（近 30 天，Top 10）/),
    ).toBeInTheDocument();
    expect(screen.getByText("广东省 深圳市")).toBeInTheDocument();
    expect(screen.getByText("United States")).toBeInTheDocument();
    expect(screen.getByText("其它")).toBeInTheDocument();
  });

  it("切换时间范围后按对应 days 重新请求", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => statsResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminStatsPanel />);

    await screen.findByText("128");
    expect(String(fetchMock.mock.calls[0][0])).toContain("days=30");

    fireEvent.click(screen.getByRole("button", { name: "近 7 天" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(String(fetchMock.mock.calls[1][0])).toContain("days=7");
  });

  it("加载失败时展示错误提示", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("网络异常")),
    );
    renderWithProviders(<AdminStatsPanel />);

    await waitFor(() =>
      expect(screen.getByText("网络异常")).toBeInTheDocument()
    );
  });
});
