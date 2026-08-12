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
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">用户管理</h2>
        <form onSubmit={search} className="flex w-full gap-2 sm:w-auto">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="按邮箱或昵称搜索"
            className="input sm:w-64"
          />
          <button type="submit" className="btn btn-primary">
            搜索
          </button>
        </form>
      </div>

      {message && (
        <p className="alert alert-success" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      )}

      {passwordTarget && (
        <form
          onSubmit={submitResetPassword}
          className="animate-fade-up flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary-soft p-3"
        >
          <span className="text-sm text-foreground">
            为 {passwordTarget.email} 设置新密码：
          </span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="至少 8 位"
            className="input min-w-40 flex-1"
            autoFocus
          />
          <button type="submit" className="btn btn-primary">
            确认重置
          </button>
          <button
            type="button"
            onClick={() => setPasswordTarget(null)}
            className="btn btn-secondary"
          >
            取消
          </button>
        </form>
      )}

      {confirmTarget && (
        <div className="animate-fade-up flex flex-wrap items-center gap-2 rounded-xl border border-warning/30 bg-warning-soft p-3">
          <span className="text-sm text-foreground">
            确定{confirmTarget.action === "toggle" ? "禁用/启用" : "重置 2FA"}
            {confirmTarget.user.email} 吗？
          </span>
          <button onClick={runConfirm} className="btn btn-primary">
            确认
          </button>
          <button
            onClick={() => setConfirmTarget(null)}
            className="btn btn-secondary"
          >
            取消
          </button>
        </div>
      )}

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>邮箱</th>
              <th>昵称</th>
              <th>角色</th>
              <th>状态</th>
              <th className="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.nickname}</td>
                <td>
                  {user.role === "admin" ? (
                    <span className="badge badge-primary">{user.role}</span>
                  ) : (
                    <span className="badge badge-muted">{user.role}</span>
                  )}
                </td>
                <td>
                  {user.status === "active" ? (
                    <span className="badge badge-success">{user.status}</span>
                  ) : (
                    <span className="badge badge-danger">{user.status}</span>
                  )}
                </td>
                <td>
                  <div className="flex justify-end gap-1.5">
                    <button
                      onClick={() => toggleStatus(user)}
                      disabled={user.id === currentAdminId}
                      title={user.id === currentAdminId ? "不能禁用自己" : undefined}
                      className="btn btn-secondary px-2.5 py-1.5 text-xs"
                    >
                      {user.status === "active" ? "禁用" : "启用"}
                    </button>
                    <button
                      onClick={() => startResetPassword(user)}
                      className="btn btn-secondary px-2.5 py-1.5 text-xs"
                    >
                      重置密码
                    </button>
                    <button
                      onClick={() => startReset2fa(user)}
                      className="btn btn-secondary px-2.5 py-1.5 text-xs"
                    >
                      重置 2FA
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
