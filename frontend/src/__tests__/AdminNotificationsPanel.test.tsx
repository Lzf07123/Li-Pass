import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminNotificationsPanel } from "../pages/AdminNotificationsPanel";
import { renderWithProviders } from "../test/renderWithProviders";

function historyResponse(items: unknown[] = []) {
  return new Response(JSON.stringify({ items, total: items.length }), {
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
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
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
    fireEvent.change(screen.getByLabelText("收件人邮箱（每行一个）"), {
      target: { value: "a@example.com\nb@example.com" },
    });
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
      expect(body.emails).toEqual(["a@example.com", "b@example.com"]);
      expect(body.in_site).toBe(true);
      expect(body.email).toBe(true);
    });
  });
});
