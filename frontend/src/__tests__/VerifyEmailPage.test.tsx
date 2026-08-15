import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VerifyEmailPage } from "../pages/VerifyEmailPage";
import { renderWithProviders } from "../test/renderWithProviders";

function mockVerifySuccess() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "邮箱已验证" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("携带安全 next 时验证成功后跳回原授权地址", async () => {
    mockVerifySuccess();
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "", origin: original.origin },
      writable: true,
      configurable: true,
    });
    const next = `${original.origin}/oauth2/authorize?code_challenge=x`;

    renderWithProviders(<VerifyEmailPage />, [
      `/verify-email?email=a%40example.com&next=${encodeURIComponent(next)}`,
    ]);
    await screen.findByLabelText("验证码");
    fireEvent.change(screen.getByLabelText("验证码"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "验证" }));

    await waitFor(() => expect(window.location.href).toBe(next));
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });

  it("next 非同源时忽略回跳并提示去登录", async () => {
    mockVerifySuccess();
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "", origin: original.origin },
      writable: true,
      configurable: true,
    });

    renderWithProviders(<VerifyEmailPage />, [
      "/verify-email?email=a%40example.com&next=https%3A%2F%2Fevil.example%2Fsteal",
    ]);
    await screen.findByLabelText("验证码");
    expect(
      screen.getByText(
        "无法验证返回原网站的链接（域名或协议与门户不一致），验证完成后将停留在门户个人中心。",
      ),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("验证码"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "验证" }));

    await waitFor(() => expect(screen.getByText("去登录")).toBeInTheDocument());
    expect(window.location.href).toBe("");
    Object.defineProperty(window, "location", {
      value: original,
      configurable: true,
    });
  });
});
