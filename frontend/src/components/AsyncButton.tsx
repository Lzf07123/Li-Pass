import type { ButtonHTMLAttributes, ReactNode } from "react";

import type { AsyncStatus } from "../hooks/useAsyncAction";

interface AsyncButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  status: AsyncStatus;
  loadingLabel?: string;
  successLabel?: string;
  spinner?: boolean;
  children: ReactNode;
}

const STATUS_CLASS: Record<AsyncStatus, string> = {
  idle: "",
  pending: "opacity-80",
  success: "btn-success-flash",
  error: "",
};

export function AsyncButton({
  status,
  loadingLabel = "处理中…",
  successLabel = "已完成",
  spinner = true,
  children,
  disabled,
  className = "",
  ...rest
}: AsyncButtonProps) {
  const label =
    status === "pending"
      ? loadingLabel
      : status === "success"
        ? successLabel
        : children;

  return (
    <button
      {...rest}
      disabled={disabled || status === "pending" || status === "success"}
      aria-busy={status === "pending" || undefined}
      className={`${className} ${STATUS_CLASS[status]}`.trim()}
    >
      {spinner && status === "pending" && (
        <span aria-hidden="true" className="spinner" />
      )}
      {label}
    </button>
  );
}
