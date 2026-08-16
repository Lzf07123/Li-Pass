import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminClientsPage } from "../pages/AdminClientsPage";
import { renderWithProviders } from "../test/renderWithProviders";

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
    renderWithProviders(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
  });

  it("停用某个应用时仅该行按钮显示处理中", async () => {
    const client = (id: string, name: string) => ({
      id,
      client_id: `cli_${id}`,
      name,
      description: "",
      logo_url: null,
      redirect_uris: ["http://localhost:3001/callback"],
      scopes: ["openid"],
      require_consent_every_time: false,
      is_active: true,
      created_at: "2026-08-12T00:00:00Z",
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (/\/api\/v1\/admin\/clients\/[^/]+$/.test(url)) {
        return new Promise(() => {});
      }
      if (url.includes("/blocks")) {
        return Promise.resolve(
          new Response("[]", {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify([client("1", "Demo"), client("2", "Blog")]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminClientsPage />);

    await waitFor(() => expect(screen.getByText("Blog")).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole("button", { name: "停用" })[0]);

    const pendingButton = await screen.findByRole("button", {
      name: "处理中…",
    });
    expect(pendingButton).toHaveAttribute("aria-busy", "true");

    const remaining = screen.getByRole("button", { name: "停用" });
    expect(remaining).not.toHaveAttribute("aria-busy");
    expect(remaining).toBeDisabled();
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
    renderWithProviders(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText(/bad@example\.com/)).toBeInTheDocument());
  });

  it("删除应用后从列表移除", async () => {
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
              logout_uri: null,
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
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "删除应用" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(screen.queryByText("Demo")).not.toBeInTheDocument());
    const deleteCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "DELETE"
    );
    expect(String(deleteCall?.[0])).toContain("/api/v1/admin/clients/1");
  });

  it("编辑应用并保存修改", async () => {
    const client = {
      id: "1",
      client_id: "cli_demo",
      has_secret: true,
      public: false,
      name: "Demo",
      description: "",
      logo_url: null,
      home_url: null,
      logout_uri: null,
      redirect_uris: ["http://localhost:3001/callback"],
      scopes: ["openid"],
      require_consent_every_time: false,
      is_active: true,
      created_at: "2026-08-12T00:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([client]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...client, name: "Demo 2", is_active: false }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminClientsPage />);

    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));

    const editor = screen.getByRole("group", { name: "编辑应用" });
    fireEvent.change(within(editor).getByLabelText("名称"), {
      target: { value: "Demo 2" },
    });
    fireEvent.click(
      within(editor).getByLabelText("启用该网站（停用后无法发起授权）")
    );
    fireEvent.click(within(editor).getByRole("button", { name: "保存修改" }));

    await waitFor(() => expect(screen.getByText("Demo 2")).toBeInTheDocument());
    const patchCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "PATCH"
    );
    expect(String(patchCall?.[0])).toContain("/api/v1/admin/clients/1");
    const body = JSON.parse(String((patchCall?.[1] as RequestInit | undefined)?.body));
    expect(body.name).toBe("Demo 2");
    expect(body.is_active).toBe(false);
  });

  it("重置密钥后展示新 secret", async () => {
    const client = {
      id: "1",
      client_id: "cli_demo",
      has_secret: true,
      public: false,
      name: "Demo",
      description: "",
      logo_url: null,
      home_url: null,
      logout_uri: null,
      redirect_uris: ["http://localhost:3001/callback"],
      scopes: ["openid"],
      require_consent_every_time: false,
      is_active: true,
      created_at: "2026-08-12T00:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify([client]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            active: true,
            window_minutes: 30,
            expires_in_seconds: 1800,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ client, client_secret: "new_secret_abc123" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<AdminClientsPage />);

    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    fireEvent.click(screen.getByRole("button", { name: "重置密钥" }));
    fireEvent.click(screen.getByRole("button", { name: "确认重置" }));

    await waitFor(() =>
      expect(screen.getByText("new_secret_abc123")).toBeInTheDocument()
    );
    const resetCall = fetchMock.mock.calls.find(
      (call) => (call[1] as RequestInit | undefined)?.method === "POST"
    );
    expect(String(resetCall?.[0])).toContain("/api/v1/admin/clients/1/reset-secret");
  });
});
