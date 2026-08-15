import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PasswordStrength } from "../components/PasswordStrength";
import { assessPasswordStrength } from "../hooks/usePasswordStrength";

describe("password strength", () => {
  it("按长度、大小写、数字、符号评分", () => {
    expect(assessPasswordStrength("short").level).toBe("weak");
    expect(assessPasswordStrength("abcdefgh").level).toBe("weak");
    expect(assessPasswordStrength("password123").level).toBe("medium");
    expect(assessPasswordStrength("Password123!").level).toBe("strong");
    expect(assessPasswordStrength("").label).toBe("弱");
  });

  it("密码为空时不渲染指示器", () => {
    const { container } = render(<PasswordStrength password="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("按评分显示 弱/中/强 文案", () => {
    const { rerender } = render(<PasswordStrength password="abcdefgh" />);
    expect(screen.getByText("密码强度：弱")).toBeInTheDocument();
    rerender(<PasswordStrength password="password123" />);
    expect(screen.getByText("密码强度：中")).toBeInTheDocument();
    rerender(<PasswordStrength password="Password123!" />);
    expect(screen.getByText("密码强度：强")).toBeInTheDocument();
  });
});
