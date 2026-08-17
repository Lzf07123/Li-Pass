import { beforeEach, describe, expect, it, vi } from "vitest";

import { adminNotificationsApi, userMessagesApi } from "../api/client";

describe("通知相关 API", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("未读计数接口的 401 不派发 unauthorized 事件", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Session expired" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    const events: string[] = [];
    const listener = () => events.push("unauthorized");
    window.addEventListener("lipass:unauthorized", listener);
    await expect(userMessagesApi.unreadCount()).rejects.toThrow(
      "Session expired"
    );
    expect(events).toEqual([]);
    window.removeEventListener("lipass:unauthorized", listener);
  });

  it("发送通知请求体正确", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "n1",
          recipient_count: 2,
          email_sent: 1,
          email_failed: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await adminNotificationsApi.create({
      title: "t",
      body: "b",
      in_site: true,
      email: true,
      user_ids: ["u1"],
    });
    expect(result.recipient_count).toBe(2);
    const [, init] = fetchMock.mock.calls[0] as [unknown, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      title: "t",
      body: "b",
      in_site: true,
      email: true,
      user_ids: ["u1"],
    });
  });

  it("标记全部已读调用正确端点", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ updated: 3 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await userMessagesApi.markAllRead();
    expect(result.updated).toBe(3);
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/api/v1/me/messages/read-all"
    );
  });
});
