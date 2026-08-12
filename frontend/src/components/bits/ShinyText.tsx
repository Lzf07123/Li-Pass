import type { CSSProperties } from "react";

type ShinyTextProps = {
  text: string;
  className?: string;
  /** 基础文字色（默认跟随 currentColor） */
  color?: string;
  /** 扫光高亮色 */
  shineColor?: string;
  /** 扫光方向角度 */
  spread?: number;
  /** 单次扫光周期（秒） */
  duration?: number;
};

/**
 * ReactBits ShinyText 思路：渐变文字 + 缓慢扫光，
 * 通过 background-position 动画实现，无需 rAF。
 */
export function ShinyText({
  text,
  className = "",
  color = "currentColor",
  shineColor = "var(--portal-primary)",
  spread = 90,
  duration = 5,
}: ShinyTextProps) {
  const style: CSSProperties = {
    backgroundImage: `linear-gradient(${spread}deg, ${color} 0%, ${color} 38%, ${shineColor} 50%, ${color} 62%, ${color} 100%)`,
    backgroundSize: "200% auto",
    WebkitBackgroundClip: "text",
    backgroundClip: "text",
    WebkitTextFillColor: "transparent",
    animationDuration: `${duration}s`,
  };

  return (
    <span className={`shiny-text ${className}`} style={style}>
      {text}
    </span>
  );
}
