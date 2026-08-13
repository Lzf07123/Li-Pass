import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PasswordInput } from "../components/PasswordInput";

describe("PasswordInput", () => {
  it("点击眼睛图标切换显示/隐藏", () => {
    render(<PasswordInput className="input" aria-label="密码" />);
    const input = screen.getByLabelText("密码");

    expect(input).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "显示密码" }));
    expect(input).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "隐藏密码" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("输入框禁用时切换按钮同步禁用", () => {
    render(<PasswordInput className="input" aria-label="密码" disabled />);
    expect(screen.getByRole("button", { name: "显示密码" })).toBeDisabled();
  });
});
