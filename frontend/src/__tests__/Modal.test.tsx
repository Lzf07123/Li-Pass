import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Modal } from "../components/Modal";

describe("Modal 焦点陷阱", () => {
  it("Tab 在弹窗内循环，Shift+Tab 反向回卷", () => {
    render(
      <Modal
        open
        title="测试弹窗"
        onClose={() => undefined}
        footer={
          <>
            <button type="button">取消</button>
            <button type="button">确认</button>
          </>
        }
      >
        内容
      </Modal>
    );
    const close = screen.getByRole("button", { name: "关闭弹窗" });
    const confirm = screen.getByRole("button", { name: "确认" });

    confirm.focus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(close);

    close.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(confirm);
  });
});
