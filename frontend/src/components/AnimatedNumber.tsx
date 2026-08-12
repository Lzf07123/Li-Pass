import { useEffect, useRef, useState } from "react";

interface AnimatedNumberProps {
  value: number;
  duration?: number;
  format?: (value: number) => string;
}

const defaultFormat = new Intl.NumberFormat("zh-CN");

export function AnimatedNumber({
  value,
  duration = 600,
  format,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);
  const frame = useRef<number | null>(null);
  const formatter = format ?? ((n: number) => defaultFormat.format(n));

  useEffect(() => {
    if (value === previous.current) return;
    if (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setDisplay(value);
      previous.current = value;
      return;
    }

    const from = previous.current;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + (value - from) * eased));
      if (progress < 1) {
        frame.current = requestAnimationFrame(tick);
      } else {
        previous.current = value;
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [duration, value]);

  return <span>{formatter(display)}</span>;
}
