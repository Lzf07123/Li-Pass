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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState<"status" | "delete" | null>(null);
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [batchDeletePassword, setBatchDeletePassword] = useState("");
  const [batchInviteOpen, setBatchInviteOpen] = useState(false);
  const [batchInviteText, setBatchInviteText] = useState("");
  const [batchInviteBusy, setBatchInviteBusy] = useState(false);
  const toast = useToast();

  const selectableUsers = users.filter(
    (user) => user.id !== currentAdminId && user.kind !== "invite",
  );
  const allSelected =
    selectableUsers.length > 0 &&
    selectableUsers.every((user) => selected.has(user.id));

  const STATUS_LABEL: Record<string, string> = {
    active: "正常",
    disabled: "已禁用",
    invited: "待注册",
    expired: "已过期",
  };

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
    setSelected(new Set());
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
      await load(query);
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送邀请失败");
    } finally {
      setInviteBusy(false);
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(selectableUsers.map((user) => user.id)));
    }
  }

  async function runBatchStatus(status: "active" | "disabled") {
    const ids = Array.from(selected);
    if (ids.length === 0 || bulkBusy !== null) return;
    setBulkBusy("status");
    try {
      const result = await adminUsersApi.batchUpdate(ids, { status });
      setSelected(new Set());
      await load(query);
      toast.success(
        `已${status === "active" ? "启用" : "禁用"} ${result.updated.length} 个账号`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "批量操作失败");
    } finally {
      setBulkBusy(null);
    }
  }

  async function submitBatchDelete(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ids = Array.from(selected);
    if (ids.length === 0 || bulkBusy !== null) return;
    if (!batchDeletePassword) {
      toast.error("请输入你的当前密码以确认批量删除");
      return;
    }
    setBulkBusy("delete");
    try {
      const result = await adminUsersApi.batchDelete(ids, batchDeletePassword);
      setBatchDeleteOpen(false);
      setBatchDeletePassword("");
      setSelected(new Set());
      await load(query);
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "批量删除失败");
    } finally {
      setBulkBusy(null);
    }
  }

  async function submitBatchInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (batchInviteBusy) return;
    const emails = batchInviteText
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (emails.length === 0) {
      toast.error("请至少填写一个邮箱");
      return;
    }
    setBatchInviteBusy(true);
    try {
      const result = await adminUsersApi.batchInvite(emails);
      setBatchInviteOpen(false);
      setBatchInviteText("");
      await load(query);
      const summary = [`已发送 ${result.invited.length} 封邀请`];
      if (result.skipped.length > 0) {
        summary.push(`跳过 ${result.skipped.length} 个（已注册或已邀请）`);
      }
      toast.success(summary.join("，"));
      if (result.failed.length > 0) {
        toast.error(
          `${result.failed.length} 封发送失败：${result.failed
            .map((item) => item.email)
            .join("、")}`,
        );
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "批量邀请失败");
    } finally {
      setBatchInviteBusy(false);
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
          <button
            onClick={() => {
              setBatchInviteText("");
              setBatchInviteOpen(true);
            }}
            className="btn btn-secondary"
          >
            批量邀请
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

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary-soft px-4 py-2">
          <span className="text-sm font-medium text-foreground">
            已选 {selected.size} 个账号
          </span>
          <button
            onClick={() => void runBatchStatus("active")}
            disabled={bulkBusy !== null}
            className="btn btn-secondary px-2.5 py-1.5 text-xs"
          >
            批量启用
          </button>
          <button
            onClick={() => void runBatchStatus("disabled")}
            disabled={bulkBusy !== null}
            className="btn btn-secondary px-2.5 py-1.5 text-xs"
          >
            批量禁用
          </button>
          <button
            onClick={() => {
              setBatchDeletePassword("");
              setBatchDeleteOpen(true);
            }}
            disabled={bulkBusy !== null}
            className="btn btn-danger px-2.5 py-1.5 text-xs"
          >
            批量删除
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="btn-link text-xs"
          >
            取消选择
          </button>
        </div>
      )}

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th className="w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="全选用户"
                />
              </th>
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
                <td>
                  <input
                    type="checkbox"
                    checked={selected.has(user.id)}
                    disabled={
                      user.id === currentAdminId || user.kind === "invite"
                    }
                    onChange={() => toggleSelect(user.id)}
                    aria-label={`选择 ${user.email}`}
                  />
                </td>
                <td>{user.email}</td>
                <td>{user.nickname || "—"}</td>
                <td>
                  {user.role === null ? (
                    "—"
                  ) : user.role === "admin" ? (
                    <span className="badge badge-primary">{user.role}</span>
                  ) : (
                    <span className="badge badge-muted">{user.role}</span>
                  )}
                </td>
                <td>
                  {user.status === "active" ? (
                    <span
                      className="badge badge-success"
                      title={user.expires_at ? `邀请有效期至 ${new Date(user.expires_at).toLocaleString("zh-CN")}` : undefined}
                    >
                      {STATUS_LABEL[user.status] ?? user.status}
                    </span>
                  ) : user.status === "disabled" || user.status === "expired" ? (
                    <span
                      className="badge badge-danger"
                      title={user.expires_at ? `邀请有效期至 ${new Date(user.expires_at).toLocaleString("zh-CN")}` : undefined}
                    >
                      {STATUS_LABEL[user.status] ?? user.status}
                    </span>
                  ) : (
                    <span
                      className="badge badge-warning"
                      title={user.expires_at ? `邀请有效期至 ${new Date(user.expires_at).toLocaleString("zh-CN")}` : undefined}
                    >
                      {STATUS_LABEL[user.status] ?? user.status}
                    </span>
                  )}
                </td>
                <td>
                  {user.kind === "invite" ? (
                    <span className="text-sm text-muted">—</span>
                  ) : (
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
                  )}
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

      <Modal
        open={batchDeleteOpen}
        onClose={() => {
          if (bulkBusy !== "delete") setBatchDeleteOpen(false);
        }}
        title="批量删除账号"
        intent="danger"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setBatchDeleteOpen(false)}
              disabled={bulkBusy === "delete"}
            >
              取消
            </button>
            <button
              type="submit"
              form="batch-delete-user-form"
              className="btn btn-danger"
              disabled={bulkBusy === "delete"}
            >
              {bulkBusy === "delete" ? "处理中…" : "永久删除"}
            </button>
          </>
        }
      >
        <form
          id="batch-delete-user-form"
          onSubmit={submitBatchDelete}
          className="space-y-3"
        >
          <p className="text-foreground">
            将永久删除选中的 {selected.size} 个账号及其会话、授权记录、恢复码与头像等全部数据，
            此操作不可恢复。
          </p>
          <label className="block">
            <span className="label">你的当前密码</span>
            <input
              type="password"
              value={batchDeletePassword}
              onChange={(e) => setBatchDeletePassword(e.target.value)}
              placeholder="输入管理员当前密码确认"
              className="input"
              autoComplete="current-password"
              autoFocus
            />
          </label>
        </form>
      </Modal>

      <Modal
        open={batchInviteOpen}
        onClose={() => {
          if (!batchInviteBusy) setBatchInviteOpen(false);
        }}
        title="批量邀请注册"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setBatchInviteOpen(false)}
              disabled={batchInviteBusy}
            >
              取消
            </button>
            <button
              type="submit"
              form="batch-invite-user-form"
              className="btn btn-primary"
              disabled={batchInviteBusy}
            >
              {batchInviteBusy ? "处理中…" : "发送邀请"}
            </button>
          </>
        }
      >
        <form
          id="batch-invite-user-form"
          onSubmit={submitBatchInvite}
          className="space-y-3"
        >
          <label className="block">
            <span className="label">受邀邮箱（每行一个）</span>
            <textarea
              value={batchInviteText}
              onChange={(e) => setBatchInviteText(e.target.value)}
              className="input min-h-32 resize-y"
              placeholder={"alice@example.com\nbob@example.com"}
              autoFocus
            />
          </label>
          <p className="text-xs text-muted">
            每个邮箱将收到一封含唯一链接的邀请邮件；已注册或已有未消费邀请的邮箱会自动跳过。
          </p>
        </form>
      </Modal>
    </section>
  );
}
