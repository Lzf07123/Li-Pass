import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { StatusIcon } from "./bits/StatusIcon";
import {
  ToastContext,
  type ToastAction,
  type ToastApi,
  type ToastOptions,
  type ToastType,
} from "./toastContext";

interface ToastItem {
  id: number;
  type: ToastType;
  title?: string;
  message: ReactNode;
  duration: number;
  action?: ToastAction;
  leaving: boolean;
}

const DEFAULT_DURATION: Record<ToastType, number> = {
  success: 3500,
  error: 6000,
  warning: 6000,
  info: 4000,
};

const DEFAULT_TITLES: Record<ToastType, string> = {
  success: "操作成功",
  error: "出错了",
  warning: "请注意",
  info: "提示",
};

const EXIT_MS = 220;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const exitTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((prev) =>
      prev.some((item) => item.id === id && !item.leaving)
        ? prev.map((item) =>
            item.id === id ? { ...item, leaving: true } : item,
          )
        : prev,
    );
    const exitTimer = exitTimers.current.get(id);
    if (!exitTimer) {
      exitTimers.current.set(
        id,
        setTimeout(() => {
          exitTimers.current.delete(id);
          setToasts((prev) => prev.filter((item) => item.id !== id));
        }, EXIT_MS),
      );
    }
  }, []);

  const push = useCallback(
    (type: ToastType, message: ReactNode, options?: ToastOptions) => {
      const id = nextId.current++;
      const duration = options?.duration ?? DEFAULT_DURATION[type];
      setToasts((prev) => [
        ...prev,
        {
          id,
          type,
          title: options?.title ?? DEFAULT_TITLES[type],
          message,
          duration,
          action: options?.action,
          leaving: false,
        },
      ]);
      if (duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), duration),
        );
      }
      return id;
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (message, options) => push("success", message, options),
      error: (message, options) => push("error", message, options),
      warning: (message, options) => push("warning", message, options),
      info: (message, options) => push("info", message, options),
      dismiss,
    }),
    [push, dismiss],
  );

  useEffect(() => {
    const timersRef = timers.current;
    const exitTimersRef = exitTimers.current;
    return () => {
      timersRef.forEach((timer) => clearTimeout(timer));
      exitTimersRef.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div
          aria-live="polite"
          aria-atomic="false"
          className="toast-viewport"
        >
          {toasts.map((toast, index) => (
            <div
              key={toast.id}
              role={toast.type === "error" ? "alert" : "status"}
              style={{ "--toast-index": index } as CSSProperties}
              className={`toast toast-${toast.type} ${
                toast.leaving ? "toast-leave" : "toast-enter"
              }`}
            >
              <span className="toast-icon toast-icon-pop">
                <StatusIcon type={toast.type} className="h-4.5 w-4.5" />
              </span>
              <div className="min-w-0 flex-1 pt-0.5">
                {toast.title && <p className="toast-title">{toast.title}</p>}
                <div className="toast-message">{toast.message}</div>
              </div>
              {toast.action && (
                <button
                  type="button"
                  onClick={() => {
                    toast.action?.onClick();
                    dismiss(toast.id);
                  }}
                  className="toast-action"
                >
                  {toast.action.label}
                </button>
              )}
              <button
                type="button"
                aria-label="关闭通知"
                onClick={() => dismiss(toast.id)}
                className="toast-close"
              >
                ×
              </button>
              {toast.duration > 0 && (
                <span
                  className="toast-progress"
                  style={{ animationDuration: `${toast.duration}ms` }}
                />
              )}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}
