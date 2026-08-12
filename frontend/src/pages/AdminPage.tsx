import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { UserOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { AdminAuditPanel } from "./AdminAuditPanel";
import { AdminClientsPage } from "./AdminClientsPage";
import { AdminUsersPanel } from "./AdminUsersPanel";

type AdminTab = "users" | "clients" | "audit";

export function AdminPage() {
  const [me, setMe] = useState<UserOut | null>(null);
  const [tab, setTab] = useState<AdminTab>("users");
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .catch(() => navigate("/login"));
  }, [navigate]);

  if (!me) {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader title="管理后台" />
        <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
          <p className="text-sm text-muted">加载中…</p>
        </main>
      </div>
    );
  }
  if (me.role !== "admin") {
    return (
      <div className="min-h-screen bg-background">
        <AppHeader title="管理后台" />
        <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
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

  const tabs: { key: AdminTab; label: string }[] = [
    { key: "users", label: "用户管理" },
    { key: "clients", label: "应用管理" },
    { key: "audit", label: "审计日志" },
  ];

  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        title="管理后台"
        actions={
          <Link to="/" className="btn btn-secondary">
            返回用户中心
          </Link>
        }
      />

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-center gap-2">
          {tabs.map((item) => (
            <button
              key={item.key}
              onClick={() => setTab(item.key)}
              className={`btn ${tab === item.key ? "btn-primary" : "btn-secondary"}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        {tab === "users" && <AdminUsersPanel currentAdminId={me.id} />}
        {tab === "clients" && <AdminClientsPage />}
        {tab === "audit" && <AdminAuditPanel />}
      </main>
    </div>
  );
}
