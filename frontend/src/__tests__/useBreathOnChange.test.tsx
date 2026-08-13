import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useBreathOnChange } from "../hooks/useBreathOnChange";

describe("useBreathOnChange", () => {
  it("value 变化后返回 true，超时后复位", () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(
      ({ value }: { value: number }) => useBreathOnChange(value),
      { initialProps: { value: 1 } },
    );
    expect(result.current).toBe(false);

    rerender({ value: 2 });
    expect(result.current).toBe(true);

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(result.current).toBe(false);
    vi.useRealTimers();
  });
});
