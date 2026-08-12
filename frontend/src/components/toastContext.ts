import { createContext } from "react";
import type { ReactNode } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastOptions {
  title?: string;
  /** 自动关闭毫秒数；传 0 表示常驻，需用户手动关闭 */
  duration?: number;
  action?: ToastAction;
}

export interface ToastApi {
  push: (type: ToastType, message: ReactNode, options?: ToastOptions) => number;
  success: (message: ReactNode, options?: ToastOptions) => number;
  error: (message: ReactNode, options?: ToastOptions) => number;
  warning: (message: ReactNode, options?: ToastOptions) => number;
  info: (message: ReactNode, options?: ToastOptions) => number;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);
