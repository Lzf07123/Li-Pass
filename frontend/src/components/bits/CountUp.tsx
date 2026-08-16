import { useInView, useMotionValue, useSpring } from "motion/react";
import { useCallback, useEffect, useRef } from "react";

export type CountUpProps = {
  /** 目标数字（向上数到 to；direction=down 时表示起始值） */
  to: number;
  /** 起始数字（direction=down 时表示目标值） */
  from?: number;
  /** 计数方向：up 递增 / down 递减 */
  direction?: "up" | "down";
  /** 开始前的延迟（秒） */
  delay?: number;
  /** 动画时长（秒），由内部弹簧的 damping/stiffness 近似控制 */
  duration?: number;
  className?: string;
  /** 进入视口后开始计数 */
  startWhen?: boolean;
  /** 千位分隔符（空串表示不分组） */
  separator?: string;
  /** 动画开始回调 */
  onStart?: () => void;
  /** 动画结束回调 */
  onEnd?: () => void;
};

function getDecimalPlaces(num: number): number {
  const str = num.toString();
  if (str.includes(".")) {
    const decimals = str.split(".")[1];
    if (Number.parseInt(decimals, 10) !== 0) {
      return decimals.length;
    }
  }
  return 0;
}

/**
 * React Bits CountUp 的 TypeScript 移植版（motion/react 弹簧驱动）：
 * 进入视口后从 from 滚动到 to，支持千位分隔与小数位保持。
 * prefers-reduced-motion 或无 requestAnimationFrame 的环境直接显示目标值。
 */
export function CountUp({
  to,
  from = 0,
  direction = "up",
  delay = 0,
  duration = 2,
  className = "",
  startWhen = true,
  separator = "",
  onStart,
  onEnd,
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(direction === "down" ? to : from);

  const damping = 20 + 40 * (1 / duration);
  const stiffness = 100 * (1 / duration);
  const springValue = useSpring(motionValue, { damping, stiffness });

  const isInView = useInView(ref, { once: true, margin: "0px" });

  const prefersReducedMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hasRaf =
    typeof window !== "undefined" &&
    typeof window.requestAnimationFrame === "function";

  const target = direction === "down" ? from : to;
  const maxDecimals = Math.max(getDecimalPlaces(from), getDecimalPlaces(to));

  const formatValue = useCallback(
    (latest: number) => {
      const hasDecimals = maxDecimals > 0;
      const options: Intl.NumberFormatOptions = {
        useGrouping: Boolean(separator),
        minimumFractionDigits: hasDecimals ? maxDecimals : 0,
        maximumFractionDigits: hasDecimals ? maxDecimals : 0,
      };
      const formattedNumber = new Intl.NumberFormat(
        "en-US",
        options,
      ).format(latest);
      return separator
        ? formattedNumber.replace(/,/g, separator)
        : formattedNumber;
    },
    [maxDecimals, separator],
  );

  useEffect(() => {
    if (ref.current) {
      ref.current.textContent = formatValue(
        prefersReducedMotion ? target : direction === "down" ? to : from,
      );
    }
  }, [from, to, direction, formatValue, prefersReducedMotion, target]);

  useEffect(() => {
    if (isInView && startWhen) {
      if (typeof onStart === "function") onStart();

      // 无 rAF（SSR/测试）或减弱动效：同步落定目标值，不依赖墙钟动画。
      if (!hasRaf || prefersReducedMotion) {
        motionValue.set(target);
        if (ref.current) {
          ref.current.textContent = formatValue(target);
        }
        if (typeof onEnd === "function") onEnd();
        return;
      }

      const timeoutId = setTimeout(() => {
        motionValue.set(target);
      }, delay * 1000);

      const durationTimeoutId = setTimeout(
        () => {
          if (typeof onEnd === "function") {
            onEnd();
          }
        },
        delay * 1000 + duration * 1000,
      );

      return () => {
        clearTimeout(timeoutId);
        clearTimeout(durationTimeoutId);
      };
    }
  }, [
    isInView,
    startWhen,
    motionValue,
    direction,
    from,
    to,
    target,
    delay,
    duration,
    hasRaf,
    prefersReducedMotion,
    formatValue,
    onStart,
    onEnd,
  ]);

  useEffect(() => {
    const unsubscribe = springValue.on("change", (latest) => {
      if (ref.current && hasRaf && !prefersReducedMotion) {
        ref.current.textContent = formatValue(latest);
      }
    });
    return () => unsubscribe();
  }, [springValue, formatValue, hasRaf, prefersReducedMotion]);

  return <span className={className} ref={ref} />;
}

export default CountUp;
