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

describe("AdminSettingsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染 IP 库版本与加载状态", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(settingsResponse()));
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
    const fetchMock = vi.fn().mockImplementation(async () => settingsResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.click(screen.getByRole("button", { name: "开启自动更新" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const putCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(String(putCall?.[1] && (putCall[1] as RequestInit).body)).toContain(
      '"ip2region_auto_update_enabled":true',
    );
  });

  it("修改检查间隔发送对应 PUT 载荷", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => settingsResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminSettingsPanel />);

    await screen.findByText(/版本 v3\.17\.0/);
    fireEvent.change(screen.getByLabelText("IP 库检查间隔"), {
      target: { value: "72" },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const putCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "PUT",
    );
    expect(String(putCall?.[1] && (putCall[1] as RequestInit).body)).toContain(
      '"ip2region_update_interval_hours":72',
    );
  });

  it("点击立即检查更新提示更新结果", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo | URL) => {
        if (String(input).includes("/ip2region/update")) {
          return new Response(
            JSON.stringify({
              version: "v3.18.0",
              data_updated_at: "2026-08-14T00:00:00+00:00",
              changed: true,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
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
    );
  });
});
