import {
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminAuditPanel } from "../pages/AdminAuditPanel";
import { renderWithProviders } from "../test/renderWithProviders";

describe("AdminAuditPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("按分类筛选后重新请求并渲染分类徽章", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("category=security")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: "1",
                actor_type: "user",
                actor_id: "u1",
                action: "login_failed",
                category: "security",
                target_type: null,
                target_id: null,
                ip: "127.0.0.1",
                ip_location: "内网地址",
                detail: null,
                created_at: "2026-08-13T00:00:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminAuditPanel />);
    fireEvent.change(screen.getByLabelText("审计分类"), {
      target: { value: "security" },
    });

    await waitFor(() =>
      expect(screen.getByText("login_failed")).toBeInTheDocument()
    );
    expect(
      within(screen.getByRole("table")).getByText("安全")
    ).toBeInTheDocument();
    expect(screen.getByText("内网地址")).toBeInTheDocument();
  });

  it("筛选分类包含通知管理", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    renderWithProviders(<AdminAuditPanel />);
    fireEvent.change(screen.getByLabelText("审计分类"), {
      target: { value: "admin_notification" },
    });
    expect(
      (screen.getByLabelText("审计分类") as HTMLSelectElement).value
    ).toBe("admin_notification");
  });

  it("以中文标签渲染分类/动作/操作者", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "1",
              actor_type: "admin",
              actor_id: "u-admin",
              actor: {
                type: "admin",
                type_label: "管理员",
                id: "u-admin",
                display: "Admin · admin@example.org",
              },
              action: "admin_update_user",
              action_label: "更新用户",
              category: "admin_user",
              category_label: "用户管理",
              target_type: "user",
              target_id: "u1",
              ip: "127.0.0.1",
              ip_location: "内网地址",
              detail: { status: "active" },
              created_at: "2026-08-13T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    renderWithProviders(<AdminAuditPanel />);

    await waitFor(() =>
      expect(screen.getByText("更新用户")).toBeInTheDocument()
    );
    expect(
      within(screen.getByRole("table")).getByText("用户管理")
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("table")).getByText("管理员")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Admin · admin@example.org")
    ).toBeInTheDocument();
    // 原始动作名与操作者 id 保留可追溯性（title/次级文本）。
    expect(screen.getByTitle("admin_update_user")).toBeInTheDocument();
    expect(screen.getByTitle("u-admin")).toBeInTheDocument();
  });
});
