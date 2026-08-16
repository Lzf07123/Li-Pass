import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../components/ToastProvider";
import { useSessionIdle } from "../hooks/useSessionIdle";

function Probe({ session }: { session: Parameters<typeof useSessionIdle>[0] }) {
  useSessionIdle(session);
  return null;
}

describe("useSessionIdle", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("剩余 5 分钟提示，归零后派发 unauthorized", () => {
    vi.useFakeTimers({
      toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"],
    });
    const events: string[] = [];
    const listener = () => events.push("unauthorized");
    window.addEventListener("lipass:unauthorized", listener);

    render(
      <ToastProvider>
        <Probe
          session={{
            session_id: "s1",
            expires_at: "2099-01-01T00:00:00Z",
            last_used_at: "2026-01-01T00:00:00Z",
            idle_limit_minutes: 720,
            idle_remaining_seconds: 301,
            absolute_remaining_seconds: 99999,
          }}
        />
      </ToastProvider>
    );

    act(() => {
      vi.advanceTimersByTime(16_000);
    });
    expect(
      screen.getByText(/登录状态即将因长时间未操作过期/)
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(300_000);
    });
    expect(events).toEqual(["unauthorized"]);
    window.removeEventListener("lipass:unauthorized", listener);
  });
});
