import { beforeEach, describe, expect, it, vi } from "vitest";

import { authApi } from "../api/client";

describe("api client", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("将 422 数组 detail 转为可读消息", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [{ loc: ["body", "email"], msg: "邮箱格式不正确" }],
          }),
          { status: 422, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    await expect(
      authApi.register({ email: "x", password: "123", nickname: "a" })
    ).rejects.toThrow("邮箱格式不正确");
  });

  it("会话保护端点的 401 派发 unauthorized 事件", async () => {
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
    await expect(authApi.me()).rejects.toThrow("Session expired");
    expect(events).toEqual(["unauthorized"]);
    window.removeEventListener("lipass:unauthorized", listener);
  });

  it("登录端点的 401 不派发 unauthorized 事件", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "邮箱或密码错误" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    const events: string[] = [];
    const listener = () => events.push("unauthorized");
    window.addEventListener("lipass:unauthorized", listener);
    await expect(
      authApi.login({ email: "a@example.com", password: "x" })
    ).rejects.toThrow("邮箱或密码错误");
    expect(events).toEqual([]);
    window.removeEventListener("lipass:unauthorized", listener);
  });

  it("静默会话探针的 401 不派发 unauthorized 事件", async () => {
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
    await expect(authApi.meSilent()).rejects.toThrow("Session expired");
    expect(events).toEqual([]);
    window.removeEventListener("lipass:unauthorized", listener);
  });
});
