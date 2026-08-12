import { useCallback, useEffect, useState } from "react";

import { adminUsersApi } from "../api/client";
import type { AdminUserOut } from "../api/types";

export function AdminUsersPanel() {
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback((q = "") => {
    adminUsersApi
      .list(q)
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(query);
  }

  async function toggleStatus(user: AdminUserOut) {
    setError("");
    setMessage("");
    try {
      const nextStatus = user.status === "active" ? "disabled" : "active";
      const updated = await adminUsersApi.update(user.id, { status: nextStatus });
      setUsers(users.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function resetPassword(user: AdminUserOut) {
    const newPassword = window.prompt(`为 ${user.email} 设置新密码（至少 8 位）：`);
    if (!newPassword) return;
    setError("");
    try {
      const result = await adminUsersApi.resetPassword(user.id, newPassword);
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    }
  }

  async function reset2fa(user: AdminUserOut) {
    if (!window.confirm(`确定重置 ${user.email} 的二次验证吗？`)) return;
    setError("");
    try {
      const result = await adminUsersApi.reset2fa(user.id);
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    }
  }

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">用户管理</h2>
      <form onSubmit={search} className="mb-3 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="按邮箱或昵称搜索"
          className="flex-1 rounded border p-2"
        />
        <button type="submit" className="rounded bg-blue-600 p-2 text-white">
          搜索
        </button>
      </form>
      {message && <p className="mb-2 rounded bg-green-50 p-2 text-green-700">{message}</p>}
      {error && <p className="mb-2 rounded bg-red-50 p-2 text-red-700">{error}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="p-2">邮箱</th>
            <th className="p-2">昵称</th>
            <th className="p-2">角色</th>
            <th className="p-2">状态</th>
            <th className="p-2">操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-b">
              <td className="p-2">{user.email}</td>
              <td className="p-2">{user.nickname}</td>
              <td className="p-2">{user.role}</td>
              <td className="p-2">{user.status}</td>
              <td className="space-x-2 p-2">
                <button onClick={() => toggleStatus(user)} className="rounded bg-gray-200 p-1">
                  {user.status === "active" ? "禁用" : "启用"}
                </button>
                <button onClick={() => resetPassword(user)} className="rounded bg-gray-200 p-1">
                  重置密码
                </button>
                <button onClick={() => reset2fa(user)} className="rounded bg-gray-200 p-1">
                  重置 2FA
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
