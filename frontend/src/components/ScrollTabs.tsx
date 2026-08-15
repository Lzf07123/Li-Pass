import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

/**
 * 全局横向滑动标签容器：标签单行排列、超出宽度时左右滑动而非换行。
 *
 * - 隐藏滚动条、snap 轻吸附、overscroll 不带动页面滚动；
 * - 可滚动方向的边缘叠加主题色渐隐提示，提示滚动有余量；
 * - 挂载或活动标签（aria-current/aria-selected）变化时自动滚入视口中央，
 *   深链直达（如 /admin/audit）时活动标签始终可见。
 */
export function ScrollTabs({
  children,
  className = "",
  activeSelector = '[aria-current="page"], [aria-selected="true"]',
  fadeColor = "var(--portal-bg)",
}: {
  children: ReactNode;
  /** 作用在外层容器；管理后台等页面可传入负外边距实现移动端通栏。 */
  className?: string;
  activeSelector?: string;
  /** 边缘渐隐的起始色；置于轨道背景之上时传入轨道颜色保持统一。 */
  fadeColor?: string;
}) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const lastActiveRef = useRef<Element | null>(null);
  const [fadeStart, setFadeStart] = useState(false);
  const [fadeEnd, setFadeEnd] = useState(false);

  const updateFades = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setFadeStart(el.scrollLeft > 2);
    setFadeEnd(el.scrollLeft < max - 2);
  }, []);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    updateFades();
    el.addEventListener("scroll", updateFades, { passive: true });
    window.addEventListener("resize", updateFades);
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(updateFades);
      observer.observe(el);
    }
    return () => {
      el.removeEventListener("scroll", updateFades);
      window.removeEventListener("resize", updateFades);
      observer?.disconnect();
    };
  }, [updateFades]);

  useEffect(() => {
    const el = scrollerRef.current;
    const active = el?.querySelector<HTMLElement>(activeSelector) ?? null;
    // 仅活动节点变化时滚动（DOM 节点随 key 复用，重复渲染不会打断用户滑动）。
    if (active === lastActiveRef.current) return;
    lastActiveRef.current = active;
    if (active && typeof active.scrollIntoView === "function") {
      const reduced =
        typeof window.matchMedia === "function" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      active.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: reduced ? "auto" : "smooth",
      });
    }
  }, [children, activeSelector]);

  return (
    <div className={`relative ${className}`.trim()}>
      <div ref={scrollerRef} className="scroll-tabs">
        {children}
      </div>
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-0 left-0 z-10 w-8 transition-opacity duration-200 ${
          fadeStart ? "opacity-100" : "opacity-0"
        }`}
        style={{
          backgroundImage: `linear-gradient(to right, ${fadeColor}, transparent)`,
        }}
      />
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-0 right-0 z-10 w-8 transition-opacity duration-200 ${
          fadeEnd ? "opacity-100" : "opacity-0"
        }`}
        style={{
          backgroundImage: `linear-gradient(to left, ${fadeColor}, transparent)`,
        }}
      />
    </div>
  );
}
