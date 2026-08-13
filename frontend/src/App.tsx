import { lazy, Suspense, useEffect, useRef } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AuthSkeleton } from "./components/AuthSkeleton";
import { GuestOnly } from "./components/GuestOnly";
import { PageSkeleton } from "./components/PageSkeleton";

// 路由级代码分割：首屏只加载当前页面，管理后台/授权确认等低频页面按需下载
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((m) => ({ default: m.LoginPage }))
);
const RegisterPage = lazy(() =>
  import("./pages/RegisterPage").then((m) => ({ default: m.RegisterPage }))
);
const InviteRegisterPage = lazy(() =>
  import("./pages/InviteRegisterPage").then((m) => ({
    default: m.InviteRegisterPage,
  }))
);
const ForgotPasswordPage = lazy(() =>
  import("./pages/ForgotPasswordPage").then((m) => ({
    default: m.ForgotPasswordPage,
  }))
);
const ResetPasswordPage = lazy(() =>
  import("./pages/ResetPasswordPage").then((m) => ({
    default: m.ResetPasswordPage,
  }))
);
const VerifyEmailPage = lazy(() =>
  import("./pages/VerifyEmailPage").then((m) => ({
    default: m.VerifyEmailPage,
  }))
);
const ConsentPage = lazy(() =>
  import("./pages/ConsentPage").then((m) => ({ default: m.ConsentPage }))
);
const AdminPage = lazy(() =>
  import("./pages/AdminPage").then((m) => ({ default: m.AdminPage }))
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);

const AUTH_ROUTES = new Set([
  "/login",
  "/register",
  "/invite",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/consent",
]);

function PageFallback() {
  const { pathname } = useLocation();

  if (AUTH_ROUTES.has(pathname)) {
    return <AuthSkeleton />;
  }

  return (
    <PageSkeleton />
  );
}

export function AppRoutes() {
  const location = useLocation();
  const firstRender = useRef(true);

  useEffect(() => {
    firstRender.current = false;
  }, []);

  return (
    <div
      key={location.pathname}
      className={firstRender.current ? "min-h-screen" : "page-enter min-h-screen"}
    >
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
          <Route path="/invite" element={<InviteRegisterPage />} />
          <Route path="/forgot-password" element={<GuestOnly><ForgotPasswordPage /></GuestOnly>} />
          <Route path="/reset-password" element={<GuestOnly><ResetPasswordPage /></GuestOnly>} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/consent" element={<ConsentPage />} />
          <Route path="/admin/:tab?" element={<AdminPage />} />
          <Route path="/" element={<DashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
