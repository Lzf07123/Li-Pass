import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminNotificationsPanel } from "../pages/AdminNotificationsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function historyResponse(items: unknown[] = []) {
  return new Response(JSON.stringify({ items, total: items.length }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function usersResponse(items: unknown[]) {
  return new Response(JSON.stringify(items), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AdminNotificationsPanel", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染历史列表", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        historyResponse([
          {
            id: "n1",
            title: "维护通知",
            in_site: true,
            email: false,
            recipient_count: 2,
            email_sent: 0,
            email_failed: 0,
            created_at: "2026-08-14T10:00:00Z",
            sender_email: "admin@example.com",
            sender_nickname: "Admin",
          },
        ])
      )
    );
    renderWithProviders(<AdminNotificationsPanel />);
    await waitFor(() =>
      expect(screen.getByText("维护通知")).toBeInTheDocument()
    );
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
  });

  it("未选渠道时提示并阻止发送", async () => {
    const fetchMock = vi.fn().mockResolvedValue(historyResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "t" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "b" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "站内信" }));
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() =>
      expect(screen.getByText("至少选择一种发送渠道")).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).includes("/admin/notifications")
      )
    ).toBe(true); // 仅历史列表请求，无 POST
    expect(
      fetchMock.mock.calls.some(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST"
      )
    ).toBe(false);
  });

  it("发送通知提交正确请求体", async () => {
    const users = [
      {
        id: "u1",
        kind: "user",
        email: "a@example.com",
        nickname: "Alice",
        phone: null,
        email_verified: true,
        role: "user",
        status: "active",
        created_at: "2026-08-12T00:00:00Z",
      },
      {
        id: "u2",
        kind: "user",
        email: "b@example.com",
        nickname: "Bob",
        phone: null,
        email_verified: true,
        role: "user",
        status: "active",
        created_at: "2026-08-12T00:00:00Z",
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/v1/admin/users")) {
        return Promise.resolve(usersResponse(users));
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              id: "n1",
              recipient_count: 1,
              email_sent: 1,
              email_failed: 0,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(historyResponse());
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "你好 {nickname}" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "通知内容" },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /邮件/ }));
    fireEvent.click(screen.getByRole("radio", { name: "指定用户" }));
    await waitFor(() =>
      expect(
        screen.getByRole("checkbox", { name: "选择 a@example.com" })
      ).toBeInTheDocument()
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "选择 a@example.com" })
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: "选择 b@example.com" })
    );
    expect(screen.getByText("已选 2 人")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([input, init]) =>
          String(input).includes("/admin/notifications") &&
          init?.method === "POST"
      );
      expect(post).toBeDefined();
      const body = JSON.parse(
        String((post as [unknown, RequestInit])[1].body)
      );
      expect(body.user_ids).toEqual(["u1", "u2"]);
      expect(body.emails).toBeUndefined();
      expect(body.in_site).toBe(true);
      expect(body.email).toBe(true);
    });
  });

  it("指定用户未勾选时提示并阻止发送", async () => {
    const fetchMock = vi.fn(
      (input: RequestInfo | URL, _init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/v1/admin/users")) {
          return Promise.resolve(
            usersResponse([
              {
                id: "u1",
                kind: "user",
                email: "a@example.com",
                nickname: "Alice",
                phone: null,
                email_verified: true,
                role: "user",
                status: "active",
                created_at: "2026-08-12T00:00:00Z",
              },
            ])
          );
        }
        return Promise.resolve(historyResponse());
      }
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "t" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "b" },
    });
    fireEvent.click(screen.getByRole("radio", { name: "指定用户" }));
    await waitFor(() =>
      expect(
        screen.getByRole("checkbox", { name: "选择 a@example.com" })
      ).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() =>
      expect(screen.getByText("请选择收件人")).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST"
      )
    ).toBe(false);
  });

  it("标题或正文含未知占位符时提示并阻止发送", async () => {
    const fetchMock = vi.fn().mockResolvedValue(historyResponse());
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    fireEvent.change(screen.getByLabelText("标题"), {
      target: { value: "你好 {name}" },
    });
    fireEvent.change(screen.getByLabelText("正文"), {
      target: { value: "正文 {email}" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送通知" }));
    await waitFor(() =>
      expect(screen.getByText(/不支持的占位符：\{name\}/)).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST"
      )
    ).toBe(false);
  });

  it("撤回站内信并刷新历史", async () => {
    const item = {
      id: "n1",
      title: "维护通知",
      in_site: true,
      email: false,
      recipient_count: 2,
      email_sent: 0,
      email_failed: 0,
      recalled_at: null,
      created_at: "2026-08-14T10:00:00Z",
      sender_email: "admin@example.com",
      sender_nickname: "Admin",
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/recall")) {
        return Promise.resolve(
          new Response(JSON.stringify({ recalled: 2 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      return Promise.resolve(historyResponse([item]));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminNotificationsPanel />);
    await waitFor(() =>
      expect(screen.getByText("维护通知")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "撤回" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(
      within(dialog).getByRole("button", { name: "确认撤回" })
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/admin/notifications/n1/recall") &&
            init?.method === "POST"
        )
      ).toBe(true)
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    );
  });
});
