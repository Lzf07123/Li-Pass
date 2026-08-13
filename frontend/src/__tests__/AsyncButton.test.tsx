import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AsyncButton } from "../components/AsyncButton";

describe("AsyncButton", () => {
  it("pending 时禁用并显示 spinner 与 loading 文案", () => {
    render(
      <AsyncButton status="pending" loadingLabel="提交中…">
        提交
      </AsyncButton>,
    );
    const btn = screen.getByRole("button", { name: "提交中…" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(document.querySelector(".spinner")).not.toBeNull();
  });

  it("success 时显示成功文案并禁用", () => {
    render(
      <AsyncButton status="success" successLabel="已保存">
        保存
      </AsyncButton>,
    );
    const btn = screen.getByRole("button", { name: "已保存" });
    expect(btn).toBeDisabled();
    expect(btn.className).toContain("btn-success-flash");
  });

  it("idle 时透传 children", () => {
    render(<AsyncButton status="idle">登录</AsyncButton>);
    expect(screen.getByRole("button", { name: "登录" })).toBeEnabled();
  });
});
