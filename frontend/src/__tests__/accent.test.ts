import { describe, expect, it } from "vitest";

import { ACCENT_CLASSES, ACCENT_KEYS, accentFor } from "../lib/accent";

describe("accentFor", () => {
  it("同一输入始终返回同一色相", () => {
    expect(accentFor("app-1")).toBe(accentFor("app-1"));
    expect(accentFor("client_abc")).toBe(accentFor("client_abc"));
  });

  it("一批不同输入会分布到多个色相", () => {
    const hues = new Set(
      Array.from({ length: 120 }, (_, index) =>
        accentFor(`client-${index}`),
      ),
    );
    expect(hues.size).toBeGreaterThanOrEqual(4);
  });

  it("每个色相都有对应的样式类映射", () => {
    for (const key of ACCENT_KEYS) {
      expect(ACCENT_CLASSES[key].tile).toMatch(/^bg-accent-/);
      expect(ACCENT_CLASSES[key].tile).toMatch(/ text-accent-/);
      expect(ACCENT_CLASSES[key].text).toMatch(/^text-accent-/);
    }
  });
});
