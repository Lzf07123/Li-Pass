import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSettingsPanel } from "../pages/AdminSettingsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function settingsBody(overrides: Record<string, unknown> = {}) {
  return {
    public_registration_enabled: true,
    ip2region: {
      version: "v3.17.0",
      data_updated_at: "2026-07-09T15:52:51+00:00",
      v4_ready: true,
      v6_ready: true,
      auto_update_enabled: false,
      update_interval_hours: 24,
    },
    ...overrides,
  };
}

function settingsResponse(overrides: Record<string, unknown> = {}) {
  return new Response(JSON.stringify(settingsBody(overrides)), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function statusResponse(
  overrides: Record<string, unknown> = {},
  status = 200,
) {
  return new Response(
    JSON.stringify({
      state: "idle",
      stage: "idle",
      downloaded_bytes: 0,
      total_bytes: 0,
      percent: 0,
      version: null,
      changed: null,
      message: null,
      started_at: null,
      finished_at: null,
      ...overrides,
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function fetchMockWithStatus(statuses: Array<Record<string, unknown>>) {
  let statusCalls = 0;
  return vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/ip2region/update/status")) {
      const body =
        statuses[Math.min(statusCalls, statuses.length - 1)];
      statusCalls += 1;
      return statusResponse(body);
    }
    return settingsResponse();
  });
}

describe("AdminSettingsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染 IP 库版本与加载状态", async () => {
    vi.stubGlobal(
      "fetch",
      fetchMockWithStatus([{ state: "idle" }]),
    );
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    expect(screen.getByText(/IPv4 已加载 · IPv6 已加载/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "开启自动更新" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "立即检查更新" }),
    ).toBeInTheDocument();
  });

  it("切换自动更新发送对应 PUT 载荷", async () => {
    const fetchMock = fetchMockWithStatus([{ state: "idle" }]);
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.click(screen.getByRole("button", { name: "开启自动更新" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const putCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(String(putCall?.[1] && (putCall[1] as RequestInit).body)).toContain(
      '"ip2region_auto_update_enabled":true',
    );
  });

  it("修改检查间隔发送对应 PUT 载荷", async () => {
    const fetchMock = fetchMockWithStatus([{ state: "idle" }]);
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.change(screen.getByLabelText("IP 库检查间隔"), {
      target: { value: "72" },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const putCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(String(putCall?.[1] && (putCall[1] as RequestInit).body)).toContain(
      '"ip2region_update_interval_hours":72',
    );
  });

  it("点击立即检查更新进入后台下载并显示实时进度", async () => {
    let statusCalls = 0;
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/ip2region/update/status")) {
          statusCalls += 1;
          return statusCalls === 1
            ? statusResponse({ state: "idle" })
            : statusResponse({
                state: "running",
                stage: "downloading_v4",
                downloaded_bytes: 100,
                total_bytes: 200,
                percent: 42.5,
              });
        }
        if (url.includes("/ip2region/update")) {
          return new Response(
            JSON.stringify({
              started: true,
              status: {
                state: "running",
                stage: "checking",
                downloaded_bytes: 0,
                total_bytes: 0,
                percent: 0,
                version: null,
                changed: null,
                message: null,
                started_at: "2026-08-14T00:00:00+00:00",
                finished_at: null,
              },
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          );
        }
        return settingsResponse();
      });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.click(screen.getByRole("button", { name: "立即检查更新" }));

    await screen.findByText("后台下载中…");
    await screen.findByText("42.5%", {}, { timeout: 3000 });
    expect(screen.getByText("正在下载 IPv4 库")).toBeInTheDocument();
  });

  it("后台更新完成后刷新并提示最新版本", async () => {
    const statusBodies = [
      {
        state: "running",
        stage: "downloading_v6",
        downloaded_bytes: 200,
        total_bytes: 200,
        percent: 90,
      },
      {
        state: "success",
        stage: "installing",
        percent: 100,
        version: "v3.18.0",
        changed: true,
      },
    ];
    let statusCalls = 0;
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/ip2region/update/status")) {
          statusCalls += 1;
          const body =
            statusCalls === 1
              ? { state: "idle" }
              : statusBodies[
                  Math.min(statusCalls - 2, statusBodies.length - 1)
                ];
          return statusResponse(body);
        }
        if (url.includes("/ip2region/update")) {
          return new Response(
            JSON.stringify({
              started: true,
              status: {
                state: "running",
                stage: "checking",
                downloaded_bytes: 0,
                total_bytes: 0,
                percent: 0,
                version: null,
                changed: null,
                message: null,
                started_at: null,
                finished_at: null,
              },
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          );
        }
        return settingsResponse();
      });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.click(screen.getByRole("button", { name: "立即检查更新" }));

    await waitFor(() =>
      expect(screen.getByText("IP 库已更新到 v3.18.0")).toBeInTheDocument(),
      { timeout: 4000 },
    );
  });

  it("后台更新失败时展示错误信息", async () => {
    let statusCalls = 0;
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/ip2region/update/status")) {
          statusCalls += 1;
          return statusCalls === 1
            ? statusResponse({ state: "idle" })
            : statusResponse({
                state: "error",
                stage: "downloading_v4",
                message: "版本 v9.9.9 未列入信任清单",
              });
        }
        if (url.includes("/ip2region/update")) {
          return new Response(
            JSON.stringify({
              started: true,
              status: {
                state: "running",
                stage: "checking",
                downloaded_bytes: 0,
                total_bytes: 0,
                percent: 0,
                version: null,
                changed: null,
                message: null,
                started_at: null,
                finished_at: null,
              },
            }),
            { status: 202, headers: { "Content-Type": "application/json" } },
          );
        }
        return settingsResponse();
      });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.click(screen.getByRole("button", { name: "立即检查更新" }));

    await waitFor(() =>
      expect(
        screen.getByText("版本 v9.9.9 未列入信任清单"),
      ).toBeInTheDocument(),
      { timeout: 4000 },
    );
  });
});
