import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { gsap } from "gsap";
import type { ScrollTrigger as ScrollTriggerInstance } from "gsap/ScrollTrigger";

import "./StrokeText.css";

const DEFAULT_TEXT = "Draw Attention";

type Trigger = "mount" | "hover" | "scroll" | "loop";
type FillMode = "fade" | "wipe" | "none";

export type StrokeTextProps = {
  /** 渲染为可测量 SVG 字形的标题文案 */
  text?: string;
  /** 描边（轮廓）颜色 */
  strokeColor?: string;
  /** 轮廓绘制完成后灌入的填充色 */
  fillColor?: string;
  strokeWidth?: number;
  /** 每个字符轮廓绘制的秒数 */
  drawDuration?: number;
  /** 轮廓完成后到填充开始前的秒数 */
  fillDelay?: number;
  /** 相邻字符动画的错峰秒数 */
  stagger?: number;
  /** GSAP 缓动 */
  ease?: string;
  trigger?: Trigger;
  fillMode?: FillMode;
  /** 测量与渲染用的 SVG 字号（viewBox 响应式缩放） */
  fontSize?: number | string;
  fontWeight?: number | string;
  letterSpacing?: number | string;
  /** 从最后一个字符向前错峰绘制 */
  reverse?: boolean;
  className?: string;
  style?: CSSProperties;
};

/**
 * React Bits StrokeText 的 TypeScript 移植版：
 * 每个字符先沿轮廓描边绘制，再从左向右擦入填充色。
 * 颜色允许传入 CSS 变量（如 var(--portal-primary)），以便自动跟随明暗主题。
 */
export function StrokeText({
  text = DEFAULT_TEXT,
  strokeColor = "var(--portal-primary)",
  fillColor = "var(--portal-fg)",
  strokeWidth = 1.4,
  drawDuration = 1.6,
  fillDelay = 0.2,
  stagger = 0.05,
  ease = "power2.out",
  trigger = "mount",
  fillMode = "wipe",
  fontSize = 128,
  fontWeight = 800,
  letterSpacing = -4,
  reverse = false,
  className = "",
  style = {},
}: StrokeTextProps) {
  const rootRef = useRef<HTMLSpanElement | null>(null);
  const strokeTextRef = useRef<SVGTextElement | null>(null);
  const wipeRectRef = useRef<SVGRectElement | null>(null);

  const [box, setBox] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);

  const rawId = useId();
  const wipeId = `stroke-text-wipe-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`;

  const characters = useMemo(() => Array.from(String(text ?? "")), [text]);

  const fontSizeValue =
    typeof fontSize === "number"
      ? fontSize
      : Number.parseFloat(String(fontSize)) || 128;
  const dash = Math.max(fontSizeValue * 7, 200);

  const fontStyle = useMemo<CSSProperties>(
    () => ({
      fontSize: `${fontSizeValue}px`,
      fontWeight,
      letterSpacing: `${letterSpacing}px`,
    }),
    [fontSizeValue, fontWeight, letterSpacing],
  );

  useLayoutEffect(() => {
    const node = strokeTextRef.current;
    if (!node) return undefined;

    let cancelled = false;

    const measure = () => {
      if (cancelled || !strokeTextRef.current) return;
      let bbox: DOMRect | SVGRect;
      try {
        bbox = strokeTextRef.current.getBBox();
      } catch {
        // jsdom / 无布局环境：保持初始 viewBox，动画阶段会自动跳过
        return;
      }
      if (!bbox || !bbox.width) return;

      const pad = Math.max(Number(strokeWidth) || 1, fontSizeValue * 0.1);
      const next = {
        x: bbox.x - pad,
        y: bbox.y - pad,
        width: bbox.width + pad * 2,
        height: bbox.height + pad * 2,
      };

      setBox((prev) =>
        prev &&
        Math.abs(prev.x - next.x) < 0.5 &&
        Math.abs(prev.width - next.width) < 0.5 &&
        Math.abs(prev.y - next.y) < 0.5
          ? prev
          : next,
      );
    };

    measure();
    if (typeof document !== "undefined" && document.fonts?.ready) {
      document.fonts.ready.then(measure).catch(() => {});
    }

    return () => {
      cancelled = true;
    };
  }, [characters, fontSizeValue, fontWeight, letterSpacing, strokeWidth]);

  useEffect(() => {
    const root = rootRef.current;
    if (typeof window === "undefined" || !root || !box) return undefined;

    const strokes = Array.from(
      root.querySelectorAll<SVGTSpanElement>("[data-stroke-char]"),
    );
    const fills = Array.from(
      root.querySelectorAll<SVGTSpanElement>("[data-fill-char]"),
    );
    const wipe = wipeRectRef.current;
    if (!strokes.length) return undefined;

    const fillEnabled = fillMode !== "none";
    const useWipe = fillEnabled && fillMode === "wipe";
    const fillDuration = Math.max(0.4, drawDuration * 0.5);
    const staggerConfig = reverse ? { each: stagger, from: "end" as const } : stagger;
    const targets: (Element | SVGRectElement)[] = [...strokes, ...fills];
    if (wipe) targets.push(wipe);

    const setStart = () => {
      gsap.killTweensOf(targets);
      gsap.set(strokes, { strokeDasharray: dash, strokeDashoffset: dash });
      gsap.set(fills, { opacity: useWipe ? 1 : 0 });
      if (wipe) gsap.set(wipe, { attr: { width: 0 } });
    };

    const setEnd = () => {
      gsap.killTweensOf(targets);
      gsap.set(strokes, { strokeDasharray: dash, strokeDashoffset: 0 });
      gsap.set(fills, { opacity: fillEnabled ? 1 : 0 });
      if (wipe) gsap.set(wipe, { attr: { width: fillEnabled ? box.width : 0 } });
    };

    const prefersReducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      setEnd();
      return () => gsap.killTweensOf(targets);
    }

    const build = () => {
      setStart();
      const tl = gsap.timeline({
        paused: true,
        repeat: trigger === "loop" ? -1 : 0,
        repeatDelay: trigger === "loop" ? 0.9 : 0,
        defaults: { overwrite: "auto" },
      });

      tl.to(
        strokes,
        {
          strokeDashoffset: 0,
          duration: drawDuration,
          ease,
          stagger: staggerConfig,
        },
        0,
      );

      if (useWipe && wipe) {
        tl.to(
          wipe,
          {
            attr: { width: box.width },
            duration: fillDuration,
            ease: "power2.inOut",
          },
          drawDuration + fillDelay,
        );
      } else if (fillEnabled) {
        tl.to(
          fills,
          {
            opacity: 1,
            duration: fillDuration,
            ease: "power2.out",
            stagger: staggerConfig,
          },
          drawDuration + fillDelay,
        );
      }

      return tl;
    };

    let disposed = false;
    let timeline: ReturnType<typeof gsap.timeline> | null = null;
    let scrollTrigger: ScrollTriggerInstance | null = null;
    let removeHover: (() => void) | null = null;

    const cleanup = () => {
      removeHover?.();
      scrollTrigger?.kill();
      timeline?.kill();
      gsap.killTweensOf(targets);
    };

    if (trigger === "hover") {
      setEnd();
      const play = () => {
        timeline?.kill();
        timeline = build();
        timeline.play(0);
      };
      root.addEventListener("pointerenter", play);
      removeHover = () => root.removeEventListener("pointerenter", play);
    } else if (trigger === "scroll") {
      // 按需动态加载：ScrollTrigger 体积较大且初始化依赖 window.matchMedia，
      // mount/hover 模式无需为其付出加载成本；jsdom 等环境也天然安全。
      void import("gsap/ScrollTrigger").then(({ ScrollTrigger }) => {
        if (disposed || !rootRef.current) return;
        gsap.registerPlugin(ScrollTrigger);
        timeline = build();
        scrollTrigger = ScrollTrigger.create({
          trigger: root,
          start: "top 82%",
          once: true,
          onEnter: () => timeline?.play(0),
        });
      });
    } else {
      timeline = build();
      timeline.play(0);
    }

    return () => {
      disposed = true;
      cleanup();
    };
  }, [
    box,
    dash,
    drawDuration,
    fillDelay,
    stagger,
    ease,
    trigger,
    fillMode,
    reverse,
  ]);

  const viewBox = box
    ? `${box.x} ${box.y} ${box.width} ${box.height}`
    : `0 ${-fontSizeValue} 600 ${fontSizeValue * 1.3}`;

  return (
    <span
      ref={rootRef}
      className={`stroke-text ${trigger === "hover" ? "stroke-text--hover" : ""} ${className}`.trim()}
      style={
        {
          ...style,
          "--stroke-text-height": `${Math.round(fontSizeValue * 1.3)}px`,
        } as CSSProperties
      }
      role="img"
      aria-label={String(text ?? "")}
    >
      <svg
        className="stroke-text__svg"
        viewBox={viewBox}
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        {fillMode === "wipe" && box && (
          <defs>
            <clipPath id={wipeId} clipPathUnits="userSpaceOnUse">
              <rect
                ref={wipeRectRef}
                x={box.x}
                y={box.y}
                width="0"
                height={box.height}
              />
            </clipPath>
          </defs>
        )}

        <text
          ref={strokeTextRef}
          className="stroke-text__stroke"
          x="0"
          y="0"
          strokeWidth={strokeWidth}
          strokeLinejoin="round"
          strokeLinecap="round"
          style={{ ...fontStyle, fill: "none", stroke: strokeColor }}
        >
          {characters.map((char, index) => (
            <tspan data-stroke-char key={`s-${index}`}>
              {char}
            </tspan>
          ))}
        </text>

        <text
          className="stroke-text__fill"
          x="0"
          y="0"
          clipPath={fillMode === "wipe" && box ? `url(#${wipeId})` : undefined}
          style={{ ...fontStyle, fill: fillColor, stroke: "none" }}
        >
          {characters.map((char, index) => (
            <tspan data-fill-char key={`f-${index}`}>
              {char}
            </tspan>
          ))}
        </text>
      </svg>
    </span>
  );
}
