/**
 * 海玻璃强调色板：浅水绿主色之外的六个信息分层色相（全部雾面低饱和）。
 * 只用于装饰性小面积（图标瓦片、图例、分区规则线、Bento 标签），
 * 状态语义色（success/warning/destructive）永远不由此处替代。
 */

export const ACCENT_KEYS = [
  "ice",
  "aqua",
  "lilac",
  "sage",
  "mint",
  "sand",
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
  ice: {
    tile: "bg-accent-ice-soft text-accent-ice dark:bg-accent-ice dark:text-primary-foreground",
    text: "text-accent-ice",
  },
  aqua: {
    tile: "bg-accent-aqua-soft text-accent-aqua dark:bg-accent-aqua dark:text-primary-foreground",
    text: "text-accent-aqua",
  },
  lilac: {
    tile: "bg-accent-lilac-soft text-accent-lilac dark:bg-accent-lilac dark:text-primary-foreground",
    text: "text-accent-lilac",
  },
  sage: {
    tile: "bg-accent-sage-soft text-accent-sage dark:bg-accent-sage dark:text-primary-foreground",
    text: "text-accent-sage",
  },
  mint: {
    tile: "bg-accent-mint-soft text-accent-mint dark:bg-accent-mint dark:text-primary-foreground",
    text: "text-accent-mint",
  },
  sand: {
    tile: "bg-accent-sand-soft text-accent-sand dark:bg-accent-sand dark:text-primary-foreground",
    text: "text-accent-sand",
  },
};
