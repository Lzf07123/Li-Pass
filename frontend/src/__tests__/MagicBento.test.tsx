import { render, screen } from "@testing-library/react";
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
});
