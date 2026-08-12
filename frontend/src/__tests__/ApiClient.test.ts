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
});
