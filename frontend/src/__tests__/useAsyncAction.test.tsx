import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAsyncAction } from "../hooks/useAsyncAction";

describe("useAsyncAction", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("依次进入 pending → success，并在 successResetMs 后回到 idle", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async (n: number) => n * 2, {
        minimumPendingMs: 0,
        successResetMs: 1000,
      }),
    );

    let promise!: Promise<number | undefined>;
    act(() => {
      promise = result.current.run(4);
    });
    expect(result.current.status).toBe("pending");

    await act(async () => {
      await promise;
    });
    expect(result.current.status).toBe("success");
    expect(result.current.pending).toBe(false);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.status).toBe("idle");
  });

  it("失败时进入 error 并触发 onError，随后自动复位", async () => {
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useAsyncAction(
        async () => {
          throw new Error("boom");
        },
        { onError, minimumPendingMs: 0 },
      ),
    );

    let promise!: Promise<number | undefined>;
    act(() => {
      promise = result.current.run();
    });
    await act(async () => {
      await promise;
    });
    expect(result.current.status).toBe("error");
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "boom" }),
    );

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(result.current.status).toBe("idle");
  });

  it("pending 期间再次 run 直接返回 undefined", async () => {
    const { result } = renderHook(() =>
      useAsyncAction(async () => "ok", { minimumPendingMs: 100 }),
    );
    let first!: Promise<string | undefined>;
    act(() => {
      first = result.current.run();
    });
    const second = result.current.run();
    expect(second).resolves.toBeUndefined();
    act(() => {
      vi.advanceTimersByTime(100);
    });
    await act(async () => {
      await first;
      await second;
    });
  });
});
