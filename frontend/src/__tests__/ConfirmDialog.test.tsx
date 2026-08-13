import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfirmDialog } from "../components/ConfirmDialog";

describe("ConfirmDialog", () => {
  it("status=pending 时确认按钮显示处理中", () => {
    render(
      <ConfirmDialog
        open
        title="删除"
        message="确认？"
        status="pending"
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: "处理中…" })).toBeDisabled();
  });
});
