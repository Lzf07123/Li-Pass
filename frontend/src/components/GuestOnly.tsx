import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { authApi } from "../api/client";
import { isSafeNext } from "../lib/navigation";
import { AuthSkeleton } from "./AuthSkeleton";

/**
 * 认证页守卫：已登录用户访问登录/注册/找回密码等页面时，
 * 自动跳回首页（或安全的 next 目标），避免“手动输入 /login 又回到登录页”。
 */
export function GuestOnly({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"loading" | "guest" | "authed">("loading");
  const location = useLocation();

  useEffect(() => {
    let cancelled = false;
    authApi
      .meSilent()
      .then(() => {
        if (!cancelled) setStatus("authed");
      })
      .catch(() => {
        if (!cancelled) setStatus("guest");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "authed") {
    const rawNext = new URLSearchParams(location.search).get("next");
    const next = isSafeNext(rawNext) && rawNext ? rawNext : "/";
    return <Navigate to={next} replace />;
  }

  if (status === "loading") {
    return <AuthSkeleton />;
  }

  return <>{children}</>;
}
