import { useCallback, useEffect, useState } from "react";

import { adminUsersApi } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { useToast } from "../hooks/useToast";
import type { AdminUserOut } from "../api/types";

export function AdminUsersPanel({ currentAdminId }: { currentAdminId: string }) {
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [query, setQuery] = useState("");
  const [passwordTarget, setPasswordTarget] = useState<AdminUserOut | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmTarget, setConfirmTarget] = useState<{
    user: AdminUserOut;
    action: "toggle" | "reset2fa";
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserOut | null>(null);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createEmail, setCreateEmail] = useState("");
  const [createNickname, setCreateNickname] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteNickname, setInviteNickname] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const toast = useToast();

  const load = useCallback((q = "") => {
    adminUsersApi
      .list(q)
      .then(setUsers)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败"),
      );
  }, [toast]);

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
    try {
      const nextStatus = user.status === "active" ? "disabled" : "active";
      const updated = await adminUsersApi.update(user.id, { status: nextStatus });
      setUsers(users.map((item) => (item.id === updated.id ? updated : item)));
      setConfirmTarget(null);
      toast.success(`${user.email} 已${nextStatus === "active" ? "启用" : "禁用"}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  function startResetPassword(user: AdminUserOut) {
    setPasswordTarget(user);
    setNewPassword("");
  }

  async function submitResetPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!passwordTarget || newPassword.length < 8) {
      toast.error("新密码至少 8 位");
      return;
    }
    try {
      const result = await adminUsersApi.resetPassword(passwordTarget.id, newPassword);
      toast.success(result.message);
      setPasswordTarget(null);
      setNewPassword("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
    }
  }

  function startReset2fa(user: AdminUserOut) {
    setConfirmTarget({ user, action: "reset2fa" });
  }

  async function runReset2fa(user: AdminUserOut) {
    try {
      const result = await adminUsersApi.reset2fa(user.id);
      toast.success(result.message);
      setConfirmTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
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

  function startDelete(user: AdminUserOut) {
    setDeleteTarget(user);
    setDeletePassword("");
  }

  async function submitDelete(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!deleteTarget || deleting) return;
    if (!deletePassword) {
      toast.error("请输入你的当前密码以确认删除");
      return;
    }
    setDeleting(true);
    try {
      const result = await adminUsersApi.deleteAccount(
        deleteTarget.id,
        deletePassword,
      );
      setUsers(users.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
      setDeletePassword("");
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }

  function openCreate() {
    setCreateEmail("");
    setCreateNickname("");
    setCreatePassword("");
    setCreateOpen(true);
  }

  async function submitCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (createBusy) return;
    if (createPassword.length < 8) {
      toast.error("初始密码至少 8 位");
      return;
    }
    setCreateBusy(true);
    try {
      const created = await adminUsersApi.createAccount({
        email: createEmail,
        nickname: createNickname,
        password: createPassword,
      });
      setCreateOpen(false);
      toast.success(`账号 ${created.email} 已创建，用户可直接登录`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreateBusy(false);
    }
  }

  function openInvite() {
    setInviteEmail("");
    setInviteNickname("");
    setInviteOpen(true);
  }

  async function submitInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inviteBusy) return;
    setInviteBusy(true);
    try {
      const result = await adminUsersApi.invite({
        email: inviteEmail,
        nickname: inviteNickname || undefined,
      });
      setInviteOpen(false);
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送邀请失败");
    } finally {
      setInviteBusy(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">用户管理</h2>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <button onClick={openCreate} className="btn btn-primary">
            添加账号
          </button>
          <button onClick={openInvite} className="btn btn-secondary">
            邀请注册
          </button>
          <form onSubmit={search} className="flex w-full gap-2 sm:w-auto">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="按邮箱或昵称搜索"
              className="input sm:w-64"
            />
            <button type="submit" className="btn btn-secondary">
              搜索
            </button>
          </form>
        </div>
      </div>

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
                    <button
                      onClick={() => startDelete(user)}
                      disabled={user.id === currentAdminId || user.role === "admin"}
                      title={
                        user.id === currentAdminId
                          ? "不能删除自己的账号"
                          : user.role === "admin"
                            ? "管理员账号需先降级为普通用户"
                            : undefined
                      }
                      className="btn btn-danger px-2.5 py-1.5 text-xs"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmTarget !== null}
        title={
          confirmTarget?.action === "toggle" ? "禁用/启用用户" : "重置 2FA"
        }
        message={
          confirmTarget && (
            <span>
              确定
              {confirmTarget.action === "toggle" ? "禁用/启用" : "重置 2FA"}
              用户 {confirmTarget.user.email} 吗？
            </span>
          )
        }
        intent="warning"
        confirmLabel={confirmTarget?.action === "toggle" ? "确认" : "确认重置"}
        onConfirm={runConfirm}
        onCancel={() => setConfirmTarget(null)}
      />

      <Modal
        open={passwordTarget !== null}
        onClose={() => setPasswordTarget(null)}
        title={passwordTarget ? `重置 ${passwordTarget.email} 的密码` : "重置密码"}
        intent="warning"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setPasswordTarget(null)}
            >
              取消
            </button>
            <button
              type="submit"
              form="reset-password-form"
              className="btn btn-primary"
            >
              确认重置
            </button>
          </>
        }
      >
        <form
          id="reset-password-form"
          onSubmit={submitResetPassword}
          className="space-y-3"
        >
          <label className="block">
            <span className="label">新密码</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="至少 8 位"
              className="input"
              minLength={8}
              autoFocus
            />
          </label>
        </form>
      </Modal>

      <Modal
        open={deleteTarget !== null}
        onClose={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        title={deleteTarget ? `删除账号：${deleteTarget.email}` : "删除账号"}
        intent="danger"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              取消
            </button>
            <button
              type="submit"
              form="delete-user-form"
              className="btn btn-danger"
              disabled={deleting}
            >
              {deleting ? "处理中…" : "永久删除"}
            </button>
          </>
        }
      >
        <form
          id="delete-user-form"
          onSubmit={submitDelete}
          className="space-y-3"
        >
          <p className="text-foreground">
            删除后将永久移除该用户的会话、授权记录、恢复码与头像等全部数据，
            此操作不可恢复。
          </p>
          <label className="block">
            <span className="label">你的当前密码</span>
            <input
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder="输入管理员当前密码确认"
              className="input"
              autoComplete="current-password"
              autoFocus
            />
          </label>
        </form>
      </Modal>

      <Modal
        open={createOpen}
        onClose={() => {
          if (!createBusy) setCreateOpen(false);
        }}
        title="添加账号"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setCreateOpen(false)}
              disabled={createBusy}
            >
              取消
            </button>
            <button
              type="submit"
              form="create-user-form"
              className="btn btn-primary"
              disabled={createBusy}
            >
              {createBusy ? "处理中…" : "创建账号"}
            </button>
          </>
        }
      >
        <form
          id="create-user-form"
          onSubmit={submitCreate}
          className="space-y-3"
        >
          <label className="block">
            <span className="label">邮箱</span>
            <input
              type="email"
              value={createEmail}
              onChange={(e) => setCreateEmail(e.target.value)}
              className="input"
              autoComplete="off"
              required
              autoFocus
            />
          </label>
          <label className="block">
            <span className="label">昵称</span>
            <input
              value={createNickname}
              onChange={(e) => setCreateNickname(e.target.value)}
              className="input"
              autoComplete="off"
              required
            />
          </label>
          <label className="block">
            <span className="label">初始密码</span>
            <input
              type="password"
              value={createPassword}
              onChange={(e) => setCreatePassword(e.target.value)}
              placeholder="至少 8 位"
              className="input"
              minLength={8}
              autoComplete="new-password"
              required
            />
          </label>
          <p className="text-xs text-muted">
            管理员代建账号视为已完成邮箱验证，创建后即可登录；请通过安全渠道把初始密码告知用户。
          </p>
        </form>
      </Modal>

      <Modal
        open={inviteOpen}
        onClose={() => {
          if (!inviteBusy) setInviteOpen(false);
        }}
        title="邀请注册"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setInviteOpen(false)}
              disabled={inviteBusy}
            >
              取消
            </button>
            <button
              type="submit"
              form="invite-user-form"
              className="btn btn-primary"
              disabled={inviteBusy}
            >
              {inviteBusy ? "处理中…" : "发送邀请"}
            </button>
          </>
        }
      >
        <form
          id="invite-user-form"
          onSubmit={submitInvite}
          className="space-y-3"
        >
          <label className="block">
            <span className="label">邮箱</span>
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="input"
              autoComplete="off"
              required
              autoFocus
            />
          </label>
          <label className="block">
            <span className="label">昵称（可选，受邀者注册时可修改）</span>
            <input
              value={inviteNickname}
              onChange={(e) => setInviteNickname(e.target.value)}
              className="input"
              autoComplete="off"
            />
          </label>
          <p className="text-xs text-muted">
            受邀者将收到一封含唯一链接的邮件，点击后自行设置昵称与密码完成注册，邮箱即时验证。
          </p>
        </form>
      </Modal>
    </section>
  );
}
