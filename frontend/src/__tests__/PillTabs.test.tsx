import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PillTabs } from "../components/PillTabs";

describe("PillTabs", () => {
  it("渲染胶囊标签并标记活动项", () => {
    render(
      <MemoryRouter initialEntries={["/admin/users"]}>
        <PillTabs
          items={[
            { key: "users", label: "用户管理", to: "/admin/users" },
            { key: "audit", label: "审计日志", to: "/admin/audit" },
          ]}
          activeKey="users"
        />
      </MemoryRouter>,
    );

    const active = screen.getByRole("link", { name: "用户管理" });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(active).toHaveClass("is-active");
    expect(screen.getByRole("link", { name: "审计日志" })).not.toHaveClass(
      "is-active",
    );
  });
});
