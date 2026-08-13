import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessagesPage } from "../pages/MessagesPage";
import { renderWithProviders } from "../test/renderWithProviders";

function userResponse() {
  return new Response(
    JSON.stringify({
      id: "u1",
      email: "a@example.com",
      nickname: "Alice",
      email_verified: true,
      email_notifications: true,
      avatar_url: null,
      phone: null,
      role: "user",
      status: "active",
    }),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
}

function messagesResponse(items: unknown[], unread = 0) {
  return new Response(JSON.stringify({ items, total: items.length, unread }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MessagesPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染未读消息并可标记已读", async () => {
    const item = {
      id: "m1",
      title: "维护通知",
      body: "正文",
      sent_at: "2026-08-14T10:00:00Z",
      read: false,
    };
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/read")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/api/v1/me/messages/unread-count")) {
        return Promise.resolve(
          new Response(JSON.stringify({ unread: 1 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      if (url.includes("/api/v1/me/messages")) {
        return Promise.resolve(messagesResponse([item], 1));
      }
      if (url.endsWith("/api/v1/me")) {
        return Promise.resolve(userResponse());
      }
      return Promise.resolve(messagesResponse([item], 1));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<MessagesPage />, ["/messages"]);

    await waitFor(() =>
      expect(screen.getByText("维护通知")).toBeInTheDocument()
    );
    expect(screen.getByText(/未读 1 条/)).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "站内信，1 条未读" })
      ).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: "标记已读" }));
    await waitFor(() =>
      expect(screen.getByText(/未读 0 条/)).toBeInTheDocument()
    );
  });

  it("全部已读与删除调用对应端点", async () => {
    const items = [
      {
        id: "m1",
        title: "一",
        body: "b",
        sent_at: "2026-08-14T10:00:00Z",
        read: false,
      },
      {
        id: "m2",
        title: "二",
        body: "b",
        sent_at: "2026-08-14T09:00:00Z",
        read: false,
      },
    ];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.includes("/read-all")) {
        return Promise.resolve(
          new Response(JSON.stringify({ updated: 2 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      if (init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith("/api/v1/me/messages/unread-count")) {
        return Promise.resolve(
          new Response(JSON.stringify({ unread: 2 }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        );
      }
      if (url.includes("/api/v1/me/messages")) {
        return Promise.resolve(messagesResponse(items, 2));
      }
      if (url.endsWith("/api/v1/me")) {
        return Promise.resolve(userResponse());
      }
      return Promise.resolve(messagesResponse(items, 2));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<MessagesPage />, ["/messages"]);
    await waitFor(() => expect(screen.getByText("一")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "全部已读" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          String(input).includes("/read-all")
        )
      ).toBe(true)
    );
    fireEvent.click(screen.getAllByRole("button", { name: "删除" })[0]);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            String(input).includes("/api/v1/me/messages/m1") &&
            init?.method === "DELETE"
        )
      ).toBe(true)
    );
  });
});
