import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessageBell } from "../components/MessageBell";
import { renderWithProviders } from "../test/renderWithProviders";

describe("MessageBell", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("窗口重新可见时刷新未读数", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 1 }), { status: 200 })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unread: 3 }), { status: 200 })
      );
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<MessageBell />);
    await waitFor(() => expect(screen.getByText("1")).toBeInTheDocument());

    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(screen.getByText("3")).toBeInTheDocument());
  });
});
