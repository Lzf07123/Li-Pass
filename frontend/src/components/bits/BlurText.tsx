import { motion } from "motion/react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ElementType,
} from "react";

type KeyframeValue = number | string;

export type BlurTextProps = {
  /** 需要动画展示的文本内容 */
  text?: string;
  /** 相邻字/词之间的动画间隔（毫秒） */
  delay?: number;
  className?: string;
  /** 按词（words）还是按字母（letters）错峰入场 */
  animateBy?: "words" | "letters";
  /** 字/词出现方向 */
  direction?: "top" | "bottom";
  /** IntersectionObserver 触发阈值 */
  threshold?: number;
  /** IntersectionObserver 根边距 */
  rootMargin?: string;
  /** 自定义起始关键帧（覆盖默认的模糊+位移） */
  animationFrom?: Record<string, KeyframeValue>;
  /** 自定义目标关键帧序列（覆盖默认两段模糊消散） */
  animationTo?: Array<Record<string, KeyframeValue>>;
  /** 缓动函数（默认线性） */
  easing?: (t: number) => number;
  /** 全部动画完成后的回调 */
  onAnimationComplete?: () => void;
  /** 单个字/词动画时长（秒） */
  stepDuration?: number;
  /** 渲染标签：标题场景传 h1/h2/span 保持语义，默认 p */
  as?: ElementType;
};

function buildKeyframes(
  from: Record<string, KeyframeValue>,
  steps: Array<Record<string, KeyframeValue>>,
): Record<string, KeyframeValue[]> {
  const keys = new Set([
    ...Object.keys(from),
    ...steps.flatMap((step) => Object.keys(step)),
  ]);

  const keyframes: Record<string, KeyframeValue[]> = {};
  keys.forEach((key) => {
    keyframes[key] = [from[key], ...steps.map((step) => step[key])];
  });
  return keyframes;
}

/**
 * React Bits BlurText 的 TypeScript 移植版（motion/react）：
 * 按词/字错峰从模糊中浮现，进入视口后触发。
 * prefers-reduced-motion 下直接静态渲染，不做模糊位移动画。
 */
export function BlurText({
  text = "",
  delay = 200,
  className = "",
  animateBy = "words",
  direction = "top",
  threshold = 0.1,
  rootMargin = "0px",
  animationFrom,
  animationTo,
  easing = (t: number) => t,
  onAnimationComplete,
  stepDuration = 0.35,
  as: Tag = "p",
}: BlurTextProps) {
  const elements =
    animateBy === "words" ? text.split(" ") : Array.from(text);
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLElement | null>(null);

  const prefersReducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!ref.current || prefersReducedMotion) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.unobserve(ref.current as Element);
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold, rootMargin, prefersReducedMotion]);

  const defaultFrom = useMemo(
    () =>
      direction === "top"
        ? { filter: "blur(10px)", opacity: 0, y: -50 }
        : { filter: "blur(10px)", opacity: 0, y: 50 },
    [direction],
  );

  const defaultTo = useMemo(
    () => [
      {
        filter: "blur(5px)",
        opacity: 0.5,
        y: direction === "top" ? 5 : -5,
      },
      { filter: "blur(0px)", opacity: 1, y: 0 },
    ],
    [direction],
  );

  if (prefersReducedMotion) {
    return <Tag className={className}>{text}</Tag>;
  }

  const fromSnapshot = animationFrom ?? defaultFrom;
  const toSnapshots = animationTo ?? defaultTo;

  const stepCount = toSnapshots.length + 1;
  const totalDuration = stepDuration * (stepCount - 1);
  const times = Array.from({ length: stepCount }, (_, index) =>
    stepCount === 1 ? 0 : index / (stepCount - 1),
  );

  return (
    <Tag
      ref={ref}
      className={className}
      style={{ display: "flex", flexWrap: "wrap" }}
    >
      {elements.map((segment, index) => {
        const animateKeyframes = buildKeyframes(fromSnapshot, toSnapshots);
        const spanTransition = {
          duration: totalDuration,
          times,
          delay: (index * delay) / 1000,
          ease: easing,
        };

        return (
          <motion.span
            className="inline-block will-change-[transform,filter,opacity]"
            key={index}
            initial={fromSnapshot}
            animate={inView ? animateKeyframes : fromSnapshot}
            transition={spanTransition}
            onAnimationComplete={
              index === elements.length - 1 ? onAnimationComplete : undefined
            }
          >
            {segment === " " ? "\u00A0" : segment}
            {animateBy === "words" && index < elements.length - 1
              ? "\u00A0"
              : ""}
          </motion.span>
        );
      })}
    </Tag>
  );
}
