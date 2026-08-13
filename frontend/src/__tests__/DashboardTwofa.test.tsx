import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../pages/DashboardPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("DashboardPage 2FA", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染安全设置区", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            phone: null,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            email_otp_enabled: false,
            totp_enabled: false,
            recovery_codes_remaining: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DashboardPage />);
    await waitFor(() => expect(screen.getByText("安全设置")).toBeInTheDocument());
  });
});
