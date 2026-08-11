import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { UserOut } from "../api/types";

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "未登录");
        navigate("/login");
      });
  }, [navigate]);

  async function handleLogout() {
    await authApi.logout();
    navigate("/login");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">用户中心</h1>
        {user ? (
          <>
            <p>邮箱：{user.email}</p>
            <p>昵称：{user.nickname}</p>
            <p>邮箱已验证：{user.email_verified ? "是" : "否"}</p>
            <button onClick={handleLogout} className="w-full rounded bg-red-600 p-2 text-white">
              退出登录
            </button>
          </>
        ) : (
          <p>{error || "加载中…"}</p>
        )}
      </div>
    </main>
  );
}
