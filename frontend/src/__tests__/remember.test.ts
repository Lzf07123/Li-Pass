import { beforeEach, describe, expect, it } from "vitest";

import {
  getRememberedAccount,
  getRememberedPassword,
  persistRememberedCredentials,
} from "../lib/remember";

describe("remember credentials", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("记住账号时保存邮箱，取消勾选清除密码", () => {
    persistRememberedCredentials("a@example.com", "password123", true, false);
    expect(getRememberedAccount()).toBe("a@example.com");
    expect(getRememberedPassword()).toBeNull();

    persistRememberedCredentials("a@example.com", "password123", false, false);
    expect(getRememberedAccount()).toBeNull();
  });

  it("记住密码时同时保存账号与密码", () => {
    persistRememberedCredentials("a@example.com", "password123", true, true);
    expect(getRememberedAccount()).toBe("a@example.com");
    expect(getRememberedPassword()).toBe("password123");

    persistRememberedCredentials("a@example.com", "password123", true, false);
    expect(getRememberedAccount()).toBe("a@example.com");
    expect(getRememberedPassword()).toBeNull();
  });
});
