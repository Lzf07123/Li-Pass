/**
 * 低饱和强调色板：安全蓝主色之外的六个信息分层色相。
 * 只用于装饰性小面积（图标瓦片、图例、分区规则线、Bento 标签），
 * 状态语义色（success/warning/destructive）永远不由此处替代。
 */

export const ACCENT_KEYS = [
  "cyan",
  "teal",
  "indigo",
  "violet",
  "amber",
  "rose",
] as const;

export type AccentKey = (typeof ACCENT_KEYS)[number];

/**
 * 稳定的字符串哈希 → 色相映射：同一实体（应用 ID/邮箱）每次渲染颜色一致，
 * 页面刷新或列表重排都不会跳色。
 */
export function accentFor(id: string): AccentKey {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1) {
    hash = (hash * 31 + id.charCodeAt(index)) >>> 0;
  }
  return ACCENT_KEYS[hash % ACCENT_KEYS.length];
}

/** 每个色相的 Tailwind 语义类组合（soft 底 + strong 前景，满足 AA 对比）。 */
export const ACCENT_CLASSES: Record<
  AccentKey,
  { tile: string; text: string }
> = {
  cyan: {
    tile: "bg-accent-cyan-soft text-accent-cyan",
    text: "text-accent-cyan",
  },
  teal: {
    tile: "bg-accent-teal-soft text-accent-teal",
    text: "text-accent-teal",
  },
  indigo: {
    tile: "bg-accent-indigo-soft text-accent-indigo",
    text: "text-accent-indigo",
  },
  violet: {
    tile: "bg-accent-violet-soft text-accent-violet",
    text: "text-accent-violet",
  },
  amber: {
    tile: "bg-accent-amber-soft text-accent-amber",
    text: "text-accent-amber",
  },
  rose: {
    tile: "bg-accent-rose-soft text-accent-rose",
    text: "text-accent-rose",
  },
};
