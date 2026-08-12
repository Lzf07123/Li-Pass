import { useEffect, useRef, useState } from "react";

export function useBreathOnChange<T>(value: T, durationMs = 800): boolean {
  const [breathing, setBreathing] = useState(false);
  const previous = useRef(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (Object.is(previous.current, value)) return;
    previous.current = value;
    setBreathing(true);
    if (timer.current) clearTimeout(timer.current);
    const next = setTimeout(() => setBreathing(false), durationMs);
    timer.current = next;
    return () => {
      clearTimeout(next);
    };
  }, [durationMs, value]);

  return breathing;
}
