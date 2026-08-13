import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsentPage } from "../pages/ConsentPage";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConsentPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("同意后跳转到 redirect_url", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "r1",
            client: { name: "Demo", logo_url: null, description: "" },
            scopes: ["openid", "profile"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ redirect_url: "http://localhost:3001/callback?code=abc" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });

    renderWithProviders(<ConsentPage />, ["/consent?request_id=r1"]);
    await waitFor(() => expect(screen.getAllByText("Demo").length).toBeGreaterThan(0));
    expect(screen.getByText("OpenID 身份标识")).toBeInTheDocument();
    expect(screen.getByText("昵称与头像等基本资料")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "同意授权" }));
    await waitFor(() =>
      expect(window.location.href).toBe("http://localhost:3001/callback?code=abc")
    );
    Object.defineProperty(window, "location", { value: original, configurable: true });
  });
});
