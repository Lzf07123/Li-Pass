import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

const EASE_CSS = "cubic-bezier(0.25, 0.1, 0.25, 1)";

type FadeInProps = {
  children: ReactNode;
  className?: string;
  /** 秒；用于错峰入场 */
  delay?: number;
  /** 位移距离（px） */
  y?: number;
  duration?: number;
  /** 滚动进入视口时触发；false 表示挂载即播放 */
  inView?: boolean;
};

/**
 * 轻量滚动渐显：只动 opacity / transform，
 * 尊重 prefers-reduced-motion。
 */
export function FadeIn({
  children,
  className,
  delay = 0,
  y = 18,
  duration = 0.5,
  inView = true,
}: FadeInProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(!inView);

  useEffect(() => {
    if (!inView) return;
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.12 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [inView]);

  // 纯 CSS transition：不引入动画运行时；prefers-reduced-motion 由全局样式统一压成瞬态。
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : `translateY(${y}px)`,
        transition: `opacity ${duration}s ${EASE_CSS} ${delay}s, transform ${duration}s ${EASE_CSS} ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}
