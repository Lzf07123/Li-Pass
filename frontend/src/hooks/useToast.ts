import { useContext } from "react";

import { ToastContext } from "../components/toastContext";

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast 必须在 <ToastProvider> 内使用");
  }
  return ctx;
}
