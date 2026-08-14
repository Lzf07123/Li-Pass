import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminSessionsPanel } from "../pages/AdminSessionsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function sessionOut(overrides: Record<string, unknown> = {}) {
  return {
    id: "s1",
    user: {
      id: "u1",
      email: "alice@example.com",
      nickname: "Alice",
      role: "user",
      status: "active",
    },
    auth_method: "password",
    device_name: "Chrome on macOS",
    ip: "203.0.113.7",
    ip_location: "广东省 深圳市",
    user_agent: "Mozilla/5.0 test-agent",
    created_at: "2026-08-13T10:00:00Z",
    last_used_at: "2026-08-13T11:00:00Z",
    expires_at: "2026-08-14T11:00:00Z",
    current: false,
    ...overrides,
  };
}

function listResponse(items: unknown[], total: number) {
  return new Response(JSON.stringify({ items, total }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminSessionsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    // AnimatedNumber 在 prefers-reduced-motion 下直接显示目标值，避免依赖
    // requestAnimationFrame 的墙钟动画（CI 上不稳定）。动画行为由
    // AnimatedNumber.test.tsx 单独覆盖。
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn() })
    );
  });

  it("渲染会话列表与在线总数", async () => {
    const items = [
      sessionOut(),
      sessionOut({
        id: "s2",
        user: {
          id: "u2",
          email: "bob@example.com",
          nickname: "Bob",
          role: "user",
          status: "active",
        },
        device_name: "Safari on iPhone",
        auth_method: "totp",
      }),
    ];
    const fetchMock = vi
      .fn()
      .mockResolvedValue(listResponse(items, items.length));
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("Chrome on macOS")).toBeInTheDocument();
    expect(screen.getByText("Safari on iPhone")).toBeInTheDocument();
    expect(screen.getByText("TOTP")).toBeInTheDocument();
    expect(screen.getAllByText("广东省 深圳市").length).toBeGreaterThan(0);
    const heading = screen.getByRole("heading", { name: /会话监控/ });
    await waitFor(() =>
      expect(heading.textContent).toContain("共 2 个在线会话")
    );
  });

  it("按邮箱搜索后只请求匹配结果并重置分页", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("q=alice")) {
        return Promise.resolve(listResponse([sessionOut()], 1));
      }
      return Promise.resolve(
        listResponse(
          [
            sessionOut(),
            sessionOut({
              id: "s2",
              user: {
                id: "u2",
                email: "bob@example.com",
                nickname: "Bob",
                role: "user",
                status: "active",
              },
            }),
          ],
          2
        )
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    fireEvent.change(screen.getByPlaceholderText("按邮箱、昵称、IP 或设备搜索"), {
      target: { value: "alice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) => String(input));
      expect(urls[urls.length - 1]).toContain("q=alice");
      expect(urls[urls.length - 1]).toContain("offset=0");
    });
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("列表未加载完时点击加载更多追加下一页", async () => {
    const third = sessionOut({
      id: "s3",
      user: {
        id: "u3",
        email: "carol@example.com",
        nickname: "Carol",
        role: "user",
        status: "active",
      },
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("offset=2")) {
        return Promise.resolve(listResponse([third], 3));
      }
      return Promise.resolve(
        listResponse(
          [
            sessionOut(),
            sessionOut({
              id: "s2",
              user: {
                id: "u2",
                email: "bob@example.com",
                nickname: "Bob",
                role: "user",
                status: "active",
              },
            }),
          ],
          3
        )
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: "加载更多" }));

    await waitFor(() =>
      expect(screen.getByText("carol@example.com")).toBeInTheDocument()
    );
    expect(
      screen.queryByRole("button", { name: "加载更多" })
    ).not.toBeInTheDocument();
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls.some((url) => url.includes("offset=2"))).toBe(true);
  });

  it("确认下线后请求 DELETE 并刷新列表", async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(
          new Response(null, { status: 204 })
        );
      }
      return Promise.resolve(listResponse([sessionOut()], 1));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: "强制下线" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/alice@example\.com/)
    ).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "确认下线" }));

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const deleteCall = calls.find(
        ([input, init]) =>
          String(input).includes("/api/v1/admin/sessions/s1") &&
          init?.method === "DELETE"
      );
      expect(deleteCall).toBeDefined();
    });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });

  it("全选仅勾选非当前会话，当前会话不可勾选", async () => {
    const items = [
      sessionOut({ current: true }),
      sessionOut({
        id: "s2",
        user: {
          id: "u2",
          email: "bob@example.com",
          nickname: "Bob",
          role: "user",
          status: "active",
        },
      }),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(listResponse(items, items.length))
    );

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    const currentBox = screen.getByRole("checkbox", {
      name: "选择 alice@example.com",
    });
    expect(currentBox).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: "全选会话" }));
    expect(screen.getByText("已选 1 个会话")).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "选择 bob@example.com" })
    ).toBeChecked();
    expect(currentBox).not.toBeChecked();
  });

  it("勾选会话后批量下线并刷新列表", async () => {
    const items = [
      sessionOut(),
      sessionOut({
        id: "s2",
        user: {
          id: "u2",
          email: "bob@example.com",
          nickname: "Bob",
          role: "user",
          status: "active",
        },
      }),
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/batch-revoke")) {
        return Promise.resolve(
          new Response(JSON.stringify({ revoked: 2, skipped: 0 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(listResponse(items, items.length));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    fireEvent.click(
      screen.getByRole("checkbox", { name: "选择 alice@example.com" })
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "选择 bob@example.com" })
    );
    expect(screen.getByText("已选 2 个会话")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "批量下线" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/将强制下线选中的 2 个会话/)
    ).toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole("button", { name: "确认下线" })
    );

    await waitFor(() => {
      const batch = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).includes("/batch-revoke") && init?.method === "POST"
      );
      expect(batch).toBeDefined();
      const body = JSON.parse(
        String((batch as [unknown, RequestInit])[1].body)
      ) as { session_ids: string[] };
      expect(body.session_ids).toEqual(
        expect.arrayContaining(["s1", "s2"])
      );
    });
    await screen.findByText("已下线 2 个会话");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
    expect(screen.queryByText(/已选 \d+ 个会话/)).not.toBeInTheDocument();
  });

  it("确认后调用全部下线并刷新列表", async () => {
    const items = [
      sessionOut(),
      sessionOut({
        id: "s2",
        user: {
          id: "u2",
          email: "bob@example.com",
          nickname: "Bob",
          role: "user",
          status: "active",
        },
      }),
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/revoke-all")) {
        return Promise.resolve(
          new Response(JSON.stringify({ revoked: 2 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(listResponse(items, items.length));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: "全部下线" }));
    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/将强制下线除你当前会话外的全部在线会话/)
    ).toBeInTheDocument();
    fireEvent.click(
      within(dialog).getByRole("button", { name: "全部下线" })
    );

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/revoke-all") && init?.method === "POST"
        )
      ).toBe(true);
    });
    await screen.findByText("已下线 2 个会话");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });

  it("无在线会话时禁用全部下线", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(listResponse([], 0))
    );

    renderWithProviders(<AdminSessionsPanel />);
    await waitFor(() =>
      expect(screen.getByText(/暂无在线会话/)).toBeInTheDocument()
    );
    expect(
      screen.getByRole("button", { name: "全部下线" })
    ).toBeDisabled();
  });
});
