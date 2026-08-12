import { useCallback, useEffect, useState } from "react";

import { adminUsersApi } from "../api/client";
import type { AdminUserOut } from "../api/types";

export function AdminUsersPanel({ currentAdminId }: { currentAdminId: string }) {
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [passwordTarget, setPasswordTarget] = useState<AdminUserOut | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmTarget, setConfirmTarget] = useState<{
    user: AdminUserOut;
    action: "toggle" | "reset2fa";
  } | null>(null);

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
    setConfirmTarget({ user, action: "toggle" });
  }

  async function runToggle(user: AdminUserOut) {
    setError("");
    setMessage("");
    try {
      const nextStatus = user.status === "active" ? "disabled" : "active";
      const updated = await adminUsersApi.update(user.id, { status: nextStatus });
      setUsers(users.map((item) => (item.id === updated.id ? updated : item)));
      setConfirmTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  function startResetPassword(user: AdminUserOut) {
    setPasswordTarget(user);
    setNewPassword("");
  }

  async function submitResetPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!passwordTarget || newPassword.length < 8) {
      setError("新密码至少 8 位");
      return;
    }
    setError("");
    try {
      const result = await adminUsersApi.resetPassword(passwordTarget.id, newPassword);
      setMessage(result.message);
      setPasswordTarget(null);
      setNewPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    }
  }

  function startReset2fa(user: AdminUserOut) {
    setConfirmTarget({ user, action: "reset2fa" });
  }

  async function runReset2fa(user: AdminUserOut) {
    setError("");
    try {
      const result = await adminUsersApi.reset2fa(user.id);
      setMessage(result.message);
      setConfirmTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    }
  }

  function runConfirm() {
    if (!confirmTarget) return;
    if (confirmTarget.action === "toggle") {
      void runToggle(confirmTarget.user);
    } else {
      void runReset2fa(confirmTarget.user);
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
      {passwordTarget && (
        <form
          onSubmit={submitResetPassword}
          className="mb-3 flex items-center gap-2 rounded border border-blue-200 bg-blue-50 p-3"
        >
          <span className="text-sm">为 {passwordTarget.email} 设置新密码：</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="至少 8 位"
            className="flex-1 rounded border p-2"
            autoFocus
          />
          <button type="submit" className="rounded bg-blue-600 p-2 text-white">
            确认重置
          </button>
          <button
            type="button"
            onClick={() => setPasswordTarget(null)}
            className="rounded bg-gray-200 p-2"
          >
            取消
          </button>
        </form>
      )}
      {confirmTarget && (
        <div className="mb-3 flex items-center gap-2 rounded border border-yellow-300 bg-yellow-50 p-3">
          <span className="text-sm">
            确定{confirmTarget.action === "toggle" ? "禁用/启用" : "重置 2FA"}
            {confirmTarget.user.email} 吗？
          </span>
          <button onClick={runConfirm} className="rounded bg-blue-600 p-2 text-white">
            确认
          </button>
          <button
            onClick={() => setConfirmTarget(null)}
            className="rounded bg-gray-200 p-2"
          >
            取消
          </button>
        </div>
      )}
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
                <button
                  onClick={() => toggleStatus(user)}
                  disabled={user.id === currentAdminId}
                  title={user.id === currentAdminId ? "不能禁用自己" : undefined}
                  className="rounded bg-gray-200 p-1 disabled:opacity-50"
                >
                  {user.status === "active" ? "禁用" : "启用"}
                </button>
                <button
                  onClick={() => startResetPassword(user)}
                  className="rounded bg-gray-200 p-1"
                >
                  重置密码
                </button>
                <button
                  onClick={() => startReset2fa(user)}
                  className="rounded bg-gray-200 p-1"
                >
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
