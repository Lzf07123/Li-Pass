import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSystemPanel } from "../pages/AdminSystemPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function systemInfo(overrides: Record<string, unknown> = {}) {
  return {
    collected_at: "2026-08-14T00:00:00Z",
    app: {
      name: "Li&Pass",
      environment: "development",
      python_version: "3.12.13",
      fastapi_version: "0.115.6",
    },
    host: {
      hostname: "portal-1",
      system: "Linux",
      release: "6.8.0",
      machine: "x86_64",
      platform: "Linux",
      cpu_cores: 4,
    },
    load: { avg_1m: 1.25, avg_5m: 1.1, avg_15m: 0.9 },
    memory: {
      total_bytes: 8 * 1024 ** 3,
      used_bytes: 5 * 1024 ** 3,
      available_bytes: 3 * 1024 ** 3,
      percent: 62.5,
      process_rss_bytes: 128 * 1024 ** 2,
    },
    disk: {
      path: "/",
      total_bytes: 100 * 1024 ** 3,
      used_bytes: 40 * 1024 ** 3,
      free_bytes: 60 * 1024 ** 3,
      percent: 40,
    },
    uptime: { system_seconds: 172800, process_seconds: 3661 },
    process: { pid: 42, python_implementation: "CPython" },
    services: { database: "ok", redis: "unused" },
    ...overrides,
  };
}

function systemInfoResponse(overrides: Record<string, unknown> = {}) {
  return new Response(JSON.stringify(systemInfo(overrides)), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminSystemPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染内存、磁盘、负载、运行时长与服务状态", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(systemInfoResponse()));
    renderWithProviders(<AdminSystemPanel />);

    await waitFor(() =>
      expect(screen.getByText("62.5%")).toBeInTheDocument()
    );
    expect(screen.getByText("已用 5.0 GB / 共 8.0 GB")).toBeInTheDocument();
    expect(screen.getByText("128 MB")).toBeInTheDocument();
    expect(screen.getByText("进程 PID 42")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("1.25 / 1.10 / 0.90")).toBeInTheDocument();
    expect(screen.getByText("1 小时 1 分")).toBeInTheDocument();
    expect(screen.getByText("系统已运行 2 天 0 小时")).toBeInTheDocument();
    expect(screen.getByText("portal-1")).toBeInTheDocument();
    expect(screen.getByText("3.12.13（CPython）")).toBeInTheDocument();
    expect(screen.getByText("正常")).toBeInTheDocument();
    expect(screen.getByText("未使用")).toBeInTheDocument();
  });

  it("点击刷新重新请求并提示成功", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => systemInfoResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSystemPanel />);

    const button = await screen.findByRole("button", { name: "刷新" });
    fireEvent.click(button);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("系统信息已刷新")).toBeInTheDocument();
  });

  it("加载失败时展示错误提示", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("网络异常")),
    );
    renderWithProviders(<AdminSystemPanel />);

    await waitFor(() =>
      expect(screen.getByText("网络异常")).toBeInTheDocument()
    );
  });
});
