import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StepUp2faForm } from "../components/StepUp2faForm";
import { renderWithProviders } from "../test/renderWithProviders";

describe("StepUp2faForm", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("提交时要求密码、方式与验证码，并回传载荷", () => {
    const onSubmit = vi.fn();
    renderWithProviders(
      <StepUp2faForm
        emailOtpEnabled
        totpEnabled
        submitLabel="永久注销"
        onSubmit={onSubmit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "永久注销" }));
    expect(screen.getByText("请输入当前密码")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("当前密码"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByLabelText("验证码"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "永久注销" }));

    expect(onSubmit).toHaveBeenCalledWith({
      current_password: "password123",
      stepup_method: "email_otp",
      stepup_code: "123456",
    });
  });

  it("获取邮箱验证码调用发送接口并进入 60 秒冷却", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "验证码已发送至绑定邮箱" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(
      <StepUp2faForm
        emailOtpEnabled
        totpEnabled={false}
        submitLabel="永久注销"
        onSubmit={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "获取验证码" }));
    await waitFor(() =>
      expect(screen.getByText(/重新发送（\d+s）/)).toBeInTheDocument()
    );
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("/api/v1/me/step-up/send")
      ),
    ).toBe(true);
  });

  it("未启用任何 2FA 方式时提示无法操作", () => {
    renderWithProviders(
      <StepUp2faForm
        emailOtpEnabled={false}
        totpEnabled={false}
        submitLabel="永久注销"
        onSubmit={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("当前密码"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "永久注销" }));
    expect(
      screen.getByText("未启用任何二次验证方式，无法执行此操作")
    ).toBeInTheDocument();
  });
});
