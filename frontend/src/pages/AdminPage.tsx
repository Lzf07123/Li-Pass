import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { UserOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { FloatingBackground } from "../components/FloatingBackground";
import { PageSkeleton } from "../components/PageSkeleton";
import { SiteFooter } from "../components/SiteFooter";
import { FadeIn } from "../components/bits/FadeIn";
import { AdminAuditPanel } from "./AdminAuditPanel";
import { AdminClientsPage } from "./AdminClientsPage";
import { AdminNotificationsPanel } from "./AdminNotificationsPanel";
import { AdminSessionsPanel } from "./AdminSessionsPanel";
import { AdminSettingsPanel } from "./AdminSettingsPanel";
import { AdminStatsPanel } from "./AdminStatsPanel";
import { AdminSystemPanel } from "./AdminSystemPanel";
import { AdminUsersPanel } from "./AdminUsersPanel";

const TABS = [
  { key: "users", label: "用户管理" },
  { key: "sessions", label: "会话监控" },
  { key: "notifications", label: "通知管理" },
  { key: "clients", label: "应用管理" },
  { key: "settings", label: "站点设置" },
  { key: "system", label: "系统信息" },
  { key: "stats", label: "数据统计" },
  { key: "audit", label: "审计日志" },
] as const;

type AdminTab = (typeof TABS)[number]["key"];

export function AdminPage() {
  const [me, setMe] = useState<UserOut | null>(null);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const segment = pathname.replace(/^\/admin\/?/, "").split("/")[0];
  const tab: AdminTab = TABS.some((item) => item.key === segment)
    ? (segment as AdminTab)
    : "users";

  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .catch(() => navigate("/login"));
  }, [navigate]);

  if (!segment || tab !== segment) {
    // /admin → 规范化到 /admin/users；未知子路径同样回到默认标签。
    return <Navigate to="/admin/users" replace />;
  }
  if (!me) {
    return <PageSkeleton title="管理后台" />;
  }
  if (me.role !== "admin") {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader title="管理后台" />
        <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="card p-8 text-center">
            <p className="mb-3 text-foreground">无权访问管理后台</p>
            <Link to="/" className="btn-link">
              返回用户中心
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      {/* 环境呼吸层：管理后台极致克制，仅作呼吸点缀 */}
      <FloatingBackground
        theme="auto"
        transparent
        shapeCount={4}
        opacity={0.5}
      />
      <AppHeader
        title="管理后台"
        actions={
          <Link to="/" className="btn btn-secondary">
            返回用户中心
          </Link>
        }
      />

      <main className="relative mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-2">
          {TABS.map((item) => (
            <Link
              key={item.key}
              to={`/admin/${item.key}`}
              aria-current={tab === item.key ? "page" : undefined}
              className={`btn ${tab === item.key ? "btn-primary" : "btn-secondary"}`}
            >
              {item.label}
            </Link>
          ))}
        </div>
        <FadeIn key={tab} inView={false} delay={0.04}>
          {tab === "users" && <AdminUsersPanel currentAdminId={me.id} />}
          {tab === "sessions" && <AdminSessionsPanel />}
          {tab === "notifications" && <AdminNotificationsPanel />}
          {tab === "clients" && <AdminClientsPage />}
          {tab === "settings" && <AdminSettingsPanel />}
          {tab === "system" && <AdminSystemPanel />}
          {tab === "stats" && <AdminStatsPanel />}
          {tab === "audit" && <AdminAuditPanel />}
        </FadeIn>
      </main>
      <SiteFooter />
    </div>
  );
}
