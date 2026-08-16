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
  const rawNext = new URLSearchParams(location.search).get("next");
  const next = isSafeNext(rawNext) && rawNext ? rawNext : "/";
  const isAbsoluteNext = /^https?:\/\//i.test(next);

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

  useEffect(() => {
    // 绝对同源 next（如 OIDC 授权回调地址）无法用 React Router 内部跳转表达，
    // 恢复登录态后直接由浏览器导航过去。
    if (status === "authed" && isAbsoluteNext) {
      window.location.replace(next);
    }
  }, [status, isAbsoluteNext, next]);

  if (status === "authed") {
    if (isAbsoluteNext) {
      return null;
    }
    return <Navigate to={next} replace />;
  }

  if (status === "loading") {
    return <AuthSkeleton />;
  }

  return <>{children}</>;
}
