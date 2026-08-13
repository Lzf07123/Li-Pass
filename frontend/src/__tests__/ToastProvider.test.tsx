import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToastProvider } from "../components/ToastProvider";
import { useToast } from "../hooks/useToast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.success("已保存")}>
      触发
    </button>
  );
}

describe("ToastProvider", () => {
  it("渲染 success Toast 并带图标容器", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "触发" }));
    expect(screen.getByText("已保存")).toBeInTheDocument();
    const icon = document.querySelector(".toast-icon");
    expect(icon).not.toBeNull();
    expect(icon?.classList.contains("toast-icon-pop")).toBe(true);
  });
});
