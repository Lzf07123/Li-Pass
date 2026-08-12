import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { UserOut } from "../api/types";
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
    return <p className="p-8">加载中…</p>;
  }
  if (me.role !== "admin") {
    return (
      <main className="p-8">
        <p>无权访问管理后台</p>
        <Link to="/" className="text-blue-600">
          返回用户中心
        </Link>
      </main>
    );
  }

  const tabs: { key: AdminTab; label: string }[] = [
    { key: "users", label: "用户管理" },
    { key: "clients", label: "应用管理" },
    { key: "audit", label: "审计日志" },
  ];

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">管理后台</h1>
          <Link to="/" className="text-blue-600">
            返回用户中心
          </Link>
        </div>
        <div className="mb-6 flex gap-2">
          {tabs.map((item) => (
            <button
              key={item.key}
              onClick={() => setTab(item.key)}
              className={`rounded p-2 ${
                tab === item.key ? "bg-blue-600 text-white" : "bg-white shadow"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        {tab === "users" && <AdminUsersPanel currentAdminId={me.id} />}
        {tab === "clients" && <AdminClientsPage />}
        {tab === "audit" && <AdminAuditPanel />}
      </div>
    </main>
  );
}
