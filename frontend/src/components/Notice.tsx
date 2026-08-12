import type { ReactNode } from "react";

import { StatusIcon, type StatusType } from "./bits/StatusIcon";

export type NoticeIntent = "success" | "warning" | "error" | "info";

const INTENT_ICON: Record<NoticeIntent, StatusType> = {
  success: "success",
  warning: "warning",
  error: "error",
  info: "info",
};

export function Notice({
  intent,
  children,
}: {
  intent: NoticeIntent;
  children: ReactNode;
}) {
  return (
    <div
      role={intent === "error" ? "alert" : "status"}
      className={`notice notice-${intent}`}
    >
      <span className="notice-icon">
        <StatusIcon type={INTENT_ICON[intent]} className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
