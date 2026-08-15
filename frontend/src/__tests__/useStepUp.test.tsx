import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useStepUp } from "../hooks/useStepUp";

function statusResponse(active: boolean) {
  return new Response(
    JSON.stringify({
      active,
      window_minutes: 30,
      expires_in_seconds: active ? 1500 : 0,
    }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("useStepUp", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("refresh 拉取状态并缓存 30 秒内的结果", async () => {
    const fetchMock = vi.fn().mockResolvedValue(statusResponse(true));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useStepUp());

    await act(async () => {
      result.current.invalidate();
      const status = await result.current.refresh(true);
      expect(status?.active).toBe(true);
    });
    expect(result.current.active).toBe(true);

    await act(async () => {
      await result.current.refresh();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("verify 复核成功后立即开窗", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
            message: "身份复核成功",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useStepUp());

    await act(async () => {
      const status = await result.current.verify("password123");
      expect(status.active).toBe(true);
    });
    expect(result.current.active).toBe(true);
  });

  it("refresh 失败时返回 null 并清除缓存", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const { result } = renderHook(() => useStepUp());

    await act(async () => {
      const status = await result.current.refresh(true);
      expect(status).toBeNull();
    });
    expect(result.current.active).toBe(false);
    expect(result.current.status).toBeNull();
  });
});
