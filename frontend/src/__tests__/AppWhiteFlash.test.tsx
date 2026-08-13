import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "../App";

function Harness() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" onClick={() => navigate("/login")}>
        去登录
      </button>
      <AppRoutes />
    </>
  );
}

describe("App 路由容器", () => {
  it("首次渲染不套 page-enter 动画，避免刷新白屏", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <Harness />
      </MemoryRouter>,
    );
    expect(container.querySelector(".page-enter")).toBeNull();
  });

  it("后续路由切换仍保留 page-enter 过渡", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <Harness />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "去登录" }));
    await waitFor(() => {
      expect(container.querySelector(".page-enter")).not.toBeNull();
    });
  });
});
