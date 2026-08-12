import { useCallback, useEffect, useRef, useState } from "react";

export type AsyncStatus = "idle" | "pending" | "success" | "error";

interface UseAsyncActionOptions<TResult> {
  minimumPendingMs?: number;
  successResetMs?: number;
  onSuccess?: (result: TResult) => void;
  onError?: (error: Error) => void;
}

export function useAsyncAction<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  options: UseAsyncActionOptions<TResult> = {},
) {
  const {
    minimumPendingMs = 350,
    successResetMs = 1600,
    onSuccess,
    onError,
  } = options;
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  const mounted = useRef(true);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    mounted.current = true;
    const timersRef = timers.current;
    return () => {
      mounted.current = false;
      timersRef.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
  }, []);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | undefined> => {
      if (status === "pending") return undefined;
      const startedAt = Date.now();
      setStatus("pending");
      setError(null);
      try {
        const result = await fn(...args);
        const elapsed = Date.now() - startedAt;
        const wait = Math.max(0, minimumPendingMs - elapsed);
        if (wait > 0) {
          await new Promise((resolve) => setTimeout(resolve, wait));
        }
        if (!mounted.current) return undefined;
        setStatus("success");
        onSuccess?.(result);
        timers.current.push(
          setTimeout(() => {
            if (mounted.current) reset();
          }, successResetMs),
        );
        return result;
      } catch (err) {
        const failure = err instanceof Error ? err : new Error(String(err));
        if (!mounted.current) return undefined;
        setStatus("error");
        setError(failure);
        onError?.(failure);
        timers.current.push(
          setTimeout(() => {
            if (mounted.current) reset();
          }, 800),
        );
        return undefined;
      }
    },
    [fn, minimumPendingMs, successResetMs, onError, onSuccess, reset, status],
  );

  return { run, status, pending: status === "pending", error, reset };
}
