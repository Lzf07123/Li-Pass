import { beforeEach, describe, expect, it } from "vitest";

import {
  getRememberedAccount,
  persistRememberedAccount,
} from "../lib/remember";

describe("remember account", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("勾选时保存邮箱，取消勾选清除", () => {
    persistRememberedAccount("a@example.com", true);
    expect(getRememberedAccount()).toBe("a@example.com");

    persistRememberedAccount("a@example.com", false);
    expect(getRememberedAccount()).toBeNull();
  });

  it("持久化时顺带清理历史遗留的明文密码键", () => {
    window.localStorage.setItem("lipass.remember.password", "password123");
    persistRememberedAccount("a@example.com", true);
    expect(window.localStorage.getItem("lipass.remember.password")).toBeNull();
    expect(getRememberedAccount()).toBe("a@example.com");
  });
});
