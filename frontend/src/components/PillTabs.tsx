import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { gsap } from "gsap";

import { ScrollTabs } from "./ScrollTabs";
import "./PillTabs.css";

const EASE = "power3.easeOut";

export type PillTabItem = {
  key: string;
  label: string;
  to: string;
};

/**
 * React Bits PillNav 的标签版：胶囊标签 hover 时圆环从底部展开、
 * 旧文案上滑离场、新文案（主色前景）从下方滑入；活动标签固定为主色胶囊。
 * 保留 ScrollTabs 的横向滚动、边缘渐隐与深链居中能力。
 */
export function PillTabs({
  items,
  activeKey,
  className = "",
}: {
  items: PillTabItem[];
  activeKey: string;
  className?: string;
}) {
  const circleRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const timelines = useRef<Array<ReturnType<typeof gsap.timeline> | null>>([]);
  const activeTweens = useRef<Array<ReturnType<typeof gsap.to> | null>>([]);

  useEffect(() => {
    const circleList = circleRefs.current;
    const timelineList = timelines.current;
    const tweenList = activeTweens.current;

    const layout = () => {
      circleList.forEach((circle, index) => {
        if (!circle?.parentElement) return;
        const pill = circle.parentElement;
        const rect = pill.getBoundingClientRect();
        const { width: w, height: h } = rect;
        if (!w || !h) return;

        // 以胶囊底部中点为圆心计算能覆盖整颗胶囊的圆：
        // 半径 R、直径 D 与圆心到胶囊底边的距离 delta。
        const R = ((w * w) / 4 + h * h) / (2 * h);
        const D = Math.ceil(2 * R) + 2;
        const delta =
          Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1;
        const originY = D - delta;

        circle.style.width = `${D}px`;
        circle.style.height = `${D}px`;
        circle.style.bottom = `-${delta}px`;
        gsap.set(circle, {
          xPercent: -50,
          scale: 0,
          transformOrigin: `50% ${originY}px`,
        });

        const label = pill.querySelector<HTMLElement>(".pill-tab-label");
        const hover = pill.querySelector<HTMLElement>(
          ".pill-tab-label-hover",
        );
        if (label) gsap.set(label, { y: 0 });
        if (hover) gsap.set(hover, { y: h + 12, opacity: 0 });

        timelineList[index]?.kill();
        const tl = gsap.timeline({ paused: true });

        tl.to(
          circle,
          { scale: 1.2, xPercent: -50, duration: 2, ease: EASE, overwrite: "auto" },
          0,
        );
        if (label) {
          tl.to(
            label,
            { y: -(h + 8), duration: 2, ease: EASE, overwrite: "auto" },
            0,
          );
        }
        if (hover) {
          gsap.set(hover, { y: Math.ceil(h + 100), opacity: 0 });
          tl.to(
            hover,
            { y: 0, opacity: 1, duration: 2, ease: EASE, overwrite: "auto" },
            0,
          );
        }

        timelineList[index] = tl;
      });
    };

    layout();
    window.addEventListener("resize", layout);
    if (document.fonts?.ready) {
      document.fonts.ready.then(layout).catch(() => {});
    }

    return () => {
      window.removeEventListener("resize", layout);
      timelineList.forEach((tl) => tl?.kill());
      tweenList.forEach((tween) => tween?.kill());
    };
  }, [items]);

  const reducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const handleEnter = (index: number) => {
    const tl = timelines.current[index];
    if (!tl) return;
    activeTweens.current[index]?.kill();
    activeTweens.current[index] = tl.tweenTo(tl.duration(), {
      duration: reducedMotion ? 0 : 0.3,
      ease: EASE,
      overwrite: "auto",
    });
  };

  const handleLeave = (index: number) => {
    const tl = timelines.current[index];
    if (!tl) return;
    activeTweens.current[index]?.kill();
    activeTweens.current[index] = tl.tweenTo(0, {
      duration: reducedMotion ? 0 : 0.2,
      ease: EASE,
      overwrite: "auto",
    });
  };

  return (
    <ScrollTabs
      className={`pill-tabs ${className}`.trim()}
      fadeColor="var(--portal-surface-2)"
    >
      {items.map((item, index) => {
        const active = item.key === activeKey;
        return (
          <Link
            key={item.key}
            to={item.to}
            aria-current={active ? "page" : undefined}
            className={`pill-tab${active ? " is-active" : ""}`}
            onMouseEnter={() => handleEnter(index)}
            onMouseLeave={() => handleLeave(index)}
            onFocus={() => handleEnter(index)}
            onBlur={() => handleLeave(index)}
          >
            <span
              className="pill-tab-circle"
              aria-hidden="true"
              ref={(el) => {
                circleRefs.current[index] = el;
              }}
            />
            <span className="pill-tab-stack">
              <span className="pill-tab-label">{item.label}</span>
              <span className="pill-tab-label-hover" aria-hidden="true">
                {item.label}
              </span>
            </span>
          </Link>
        );
      })}
    </ScrollTabs>
  );
}
