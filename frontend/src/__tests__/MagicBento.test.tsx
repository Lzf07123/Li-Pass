import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MagicBento } from "../components/bits/MagicBento";

describe("MagicBento", () => {
  it("渲染全部 Bento 卡片内容", () => {
    render(
      <MagicBento
        enableSpotlight={false}
        items={[
          {
            label: "统一登录",
            title: "一次注册，处处通行",
            description: "一个账号登录所有授权网站。",
          },
          {
            label: "明示授权",
            title: "权限可见",
            description: "每次授权清晰列明权限范围。",
          },
        ]}
      />,
    );

    expect(screen.getByText("统一登录")).toBeInTheDocument();
    expect(screen.getByText("一次注册，处处通行")).toBeInTheDocument();
    expect(screen.getByText("权限可见")).toBeInTheDocument();
    expect(document.querySelectorAll(".magic-bento-card")).toHaveLength(2);
  });

  it("紧凑模式在根节点标记并取消首卡跨列", () => {
    render(
      <MagicBento
        compact
        enableSpotlight={false}
        items={[
          {
            label: "账号总数",
            title: "1,234",
            description: "启用 1,100 · 禁用 134",
            emphasize: true,
          },
          {
            label: "管理员",
            title: "5",
            description: "",
            emphasize: true,
          },
        ]}
      />,
    );

    expect(document.querySelector(".magic-bento")).toHaveClass(
      "magic-bento--compact",
    );
  });

  it("渲染卡片图标与页脚扩展内容", () => {
    render(
      <MagicBento
        enableSpotlight={false}
        items={[
          {
            label: "在线会话",
            title: "42",
            description: "当前活跃的登录会话",
            emphasize: true,
            icon: <svg data-testid="stat-icon" />,
            footer: <div data-testid="stat-footer">迷你趋势图</div>,
          },
        ]}
      />,
    );

    expect(screen.getByTestId("stat-icon")).toBeInTheDocument();
    expect(screen.getByTestId("stat-footer")).toHaveTextContent("迷你趋势图");
  });

  it("href 项渲染为路由链接", () => {
    render(
      <MemoryRouter>
        <MagicBento
          enableSpotlight={false}
          items={[
            {
              label: "在线会话",
              title: "42",
              description: "当前活跃的登录会话",
              emphasize: true,
              href: "/admin/sessions",
            },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/admin/sessions",
    );
  });

  it("item 级 accent 覆盖卡片的辉光与标签色变量", () => {
    render(
      <MagicBento
        enableSpotlight={false}
        items={[
          {
            label: "账号总数",
            title: "128",
            description: "",
            emphasize: true,
            accent: { rgb: "45, 212, 191", hex: "#2dd4bf" },
          },
        ]}
      />,
    );

    const card = document.querySelector(
      ".magic-bento-card",
    ) as HTMLElement;
    expect(card.style.getPropertyValue("--glow-color")).toBe("45, 212, 191");
    expect(card.style.getPropertyValue("--bento-label")).toBe("#2dd4bf");
  });
});
