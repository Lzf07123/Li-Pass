import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminClientsPage } from "../pages/AdminClientsPage";

describe("AdminClientsPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染应用列表", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1",
            client_id: "cli_demo",
            name: "Demo",
            description: "",
            logo_url: null,
            redirect_uris: ["http://localhost:3001/callback"],
            scopes: ["openid"],
            require_consent_every_time: false,
            is_active: true,
            created_at: "2026-08-12T00:00:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
  });

  it("渲染黑名单列表", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "1",
              client_id: "cli_demo",
              name: "Demo",
              description: "",
              logo_url: null,
              home_url: null,
              redirect_uris: ["http://localhost:3001/callback"],
              scopes: ["openid"],
              require_consent_every_time: false,
              is_active: true,
              created_at: "2026-08-12T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            { id: "b1", user_id: null, email: "bad@example.com", reason: "滥用", created_at: "2026-08-12T00:00:00Z" },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText(/bad@example\.com/)).toBeInTheDocument());
  });
});
