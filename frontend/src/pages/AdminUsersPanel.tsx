import { useCallback, useEffect, useState } from "react";

import { adminUsersApi, twofaApi } from "../api/client";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { AsyncButton } from "../components/AsyncButton";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { PasswordInput } from "../components/PasswordInput";
import { StepUpNotice } from "../components/StepUpNotice";
import { StepUp2faForm } from "../components/StepUp2faForm";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useBreathOnChange } from "../hooks/useBreathOnChange";
import { useStepUp } from "../hooks/useStepUp";
import { useToast } from "../hooks/useToast";
import type { AdminUserOut } from "../api/types";

export function AdminUsersPanel({ currentAdminId }: { currentAdminId: string }) {
  const [users, setUsers] = useState<AdminUserOut[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [passwordTarget, setPasswordTarget] = useState<AdminUserOut | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmTarget, setConfirmTarget] = useState<{
    user: AdminUserOut;
    action: "toggle" | "reset2fa" | "cancelInvite" | "removeInvite";
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUserOut | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createEmail, setCreateEmail] = useState("");
  const [createNickname, setCreateNickname] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteNickname, setInviteNickname] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [adminTwofa, setAdminTwofa] = useState<{
    email_otp_enabled: boolean;
    totp_enabled: boolean;
  } | null>(null);
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null);
  const [resetPasswordError, setResetPasswordError] = useState<string | null>(null);
  const [deletePasswordError, setDeletePasswordError] = useState<string | null>(null);
  const [batchDeleteError, setBatchDeleteError] = useState<string | null>(null);
  const [batchInviteOpen, setBatchInviteOpen] = useState(false);
  const [batchInviteText, setBatchInviteText] = useState("");
  const [inviteBusyId, setInviteBusyId] = useState<string | null>(null);
  const [adminPassword, setAdminPassword] = useState("");
  const toast = useToast();
  const stepUp = useStepUp();
  const usersBreathing = useBreathOnChange(users);

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
    cancelled: "已取消",
    used: "已使用",
  };

  const load = useCallback(
    (q = "", status = "", role = "") => {
      adminUsersApi
        .list(q, status, role)
        .then(setUsers)
        .catch((err) =>
          toast.error(err instanceof Error ? err.message : "加载失败"),
        );
    },
    [toast],
  );

  useEffect(() => {
    load();
  }, [load]);

  const refreshAction = useAsyncAction(
    async () => {
      await load(query, statusFilter, roleFilter);
      toast.success("用户列表已刷新");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "刷新失败"),
    },
  );

  function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelected(new Set());
    load(query, statusFilter, roleFilter);
  }

  function toggleStatus(user: AdminUserOut) {
    setConfirmTarget({ user, action: "toggle" });
  }

  function startResetPassword(user: AdminUserOut) {
    setPasswordTarget(user);
    setNewPassword("");
    setAdminPassword("");
    setResetPasswordError(null);
    void stepUp.refresh(true);
  }

  const resetPasswordAction = useAsyncAction(
    async (
      id: string,
      newPassword: string,
      currentPassword: string | undefined,
    ) => {
      const result = await adminUsersApi.resetPassword(
        id,
        newPassword,
        currentPassword,
      );
      toast.success(result.message);
      setPasswordTarget(null);
      setNewPassword("");
      setAdminPassword("");
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "重置失败";
        if (message.includes("需要重新验证密码")) {
          stepUp.invalidate();
          setResetPasswordError("复核已过期，请重新输入当前密码");
        } else if (message.includes("当前密码")) {
          setResetPasswordError(message);
        } else {
          toast.error(message);
        }
      },
    },
  );

  async function submitResetPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!passwordTarget || newPassword.length < 8) {
      toast.error("新密码至少 8 位");
      return;
    }
    const password = adminPassword.trim() || undefined;
    if (!password && !(await stepUp.refresh(true))?.active) {
      setResetPasswordError("请输入管理员当前密码");
      return;
    }
    await resetPasswordAction.run(
      passwordTarget.id,
      newPassword,
      password,
    );
  }

  function startReset2fa(user: AdminUserOut) {
    setAdminPassword("");
    setConfirmPasswordError(null);
    void stepUp.refresh(true);
    setConfirmTarget({ user, action: "reset2fa" });
  }

  function startCancelInvite(user: AdminUserOut) {
    setConfirmTarget({ user, action: "cancelInvite" });
  }

  function startRemoveInvite(user: AdminUserOut) {
    setConfirmTarget({ user, action: "removeInvite" });
  }

  const confirmAction = useAsyncAction(
    async (
      user: AdminUserOut,
      action: "toggle" | "reset2fa" | "cancelInvite" | "removeInvite",
      currentPassword?: string,
    ) => {
      if (action === "toggle") {
        const nextStatus = user.status === "active" ? "disabled" : "active";
        const updated = await adminUsersApi.update(user.id, {
          status: nextStatus,
        });
        setUsers((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item)),
        );
        toast.success(
          `${user.email} 已${nextStatus === "active" ? "启用" : "禁用"}`,
        );
      } else if (action === "reset2fa") {
        const result = await adminUsersApi.reset2fa(
          user.id,
          currentPassword || undefined,
        );
        toast.success(result.message);
      } else if (action === "cancelInvite") {
        const result = await adminUsersApi.cancelInvite(user.id);
        await load(query, statusFilter, roleFilter);
        toast.success(result.message);
      } else {
        const result = await adminUsersApi.deleteInvite(user.id);
        await load(query, statusFilter, roleFilter);
        toast.success(result.message);
      }
      setConfirmTarget(null);
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "操作失败";
        if (confirmTarget?.action === "reset2fa") {
          if (message.includes("需要重新验证密码")) {
            stepUp.invalidate();
            setConfirmPasswordError("复核已过期，请重新输入当前密码");
          } else if (message.includes("当前密码")) {
            setConfirmPasswordError(message);
          } else {
            toast.error(message);
          }
        } else {
          toast.error(message);
        }
      },
    },
  );

  async function runResendInvite(user: AdminUserOut) {
    if (inviteBusyId !== null) return;
    setInviteBusyId(user.id);
    try {
      const result = await adminUsersApi.resendInvite(user.id);
      await load(query, statusFilter, roleFilter);
      toast.success(result.message);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重发邀请失败");
    } finally {
      setInviteBusyId(null);
    }
  }

  async function runConfirm() {
    if (!confirmTarget) return;
    if (
      confirmTarget.action === "reset2fa" &&
      !adminPassword.trim() &&
      !(await stepUp.refresh(true))?.active
    ) {
      setConfirmPasswordError("请输入管理员当前密码");
      return;
    }
    void confirmAction.run(
      confirmTarget.user,
      confirmTarget.action,
      confirmTarget.action === "reset2fa"
        ? adminPassword.trim() || undefined
        : undefined,
    );
  }

  function startDelete(user: AdminUserOut) {
    setDeleteTarget(user);
    setDeletePasswordError(null);
    setAdminTwofa(null);
    twofaApi
      .status()
      .then(setAdminTwofa)
      .catch(() => setAdminTwofa(null));
  }

  const deleteAction = useAsyncAction(
    async (
      id: string,
      password: string,
      stepupMethod: string,
      stepupCode: string,
    ) => {
      const result = await adminUsersApi.deleteAccount(
        id,
        password,
        stepupMethod,
        stepupCode,
      );
      setUsers((prev) => prev.filter((item) => item.id !== id));
      setDeleteTarget(null);
      toast.success(result.message);
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "删除失败";
        if (message.includes("当前密码") || message.includes("二次验证")) {
          setDeletePasswordError(message);
        } else {
          toast.error(message);
        }
      },
    },
  );

  function openCreate() {
    setCreateEmail("");
    setCreateNickname("");
    setCreatePassword("");
    setCreateOpen(true);
  }

  const createAction = useAsyncAction(
    async (email: string, nickname: string, password: string) => {
      const created = await adminUsersApi.createAccount({
        email,
        nickname,
        password,
      });
      setCreateOpen(false);
      toast.success(`账号 ${created.email} 已创建，用户可直接登录`);
      load(query, statusFilter, roleFilter);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "创建失败"),
    },
  );

  async function submitCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (createPassword.length < 8) {
      toast.error("初始密码至少 8 位");
      return;
    }
    await createAction.run(createEmail, createNickname, createPassword);
  }

  function openInvite() {
    setInviteEmail("");
    setInviteNickname("");
    setInviteOpen(true);
  }

  const inviteAction = useAsyncAction(
    async (email: string, nickname: string) => {
      const result = await adminUsersApi.invite({
        email,
        nickname: nickname || undefined,
      });
      setInviteOpen(false);
      await load(query, statusFilter, roleFilter);
      toast.success(result.message);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "发送邀请失败"),
    },
  );

  async function submitInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await inviteAction.run(inviteEmail, inviteNickname);
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

  const batchStatusAction = useAsyncAction(
    async (ids: string[], status: "active" | "disabled") => {
      const result = await adminUsersApi.batchUpdate(ids, { status });
      setSelected(new Set());
      await load(query, statusFilter, roleFilter);
      toast.success(
        `已${status === "active" ? "启用" : "禁用"} ${result.updated.length} 个账号`,
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "批量操作失败"),
    },
  );

  function runBatchStatus(status: "active" | "disabled") {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    void batchStatusAction.run(ids, status);
  }

  const batchDeleteAction = useAsyncAction(
    async (
      ids: string[],
      password: string,
      stepupMethod: string,
      stepupCode: string,
    ) => {
      const result = await adminUsersApi.batchDelete(
        ids,
        password,
        stepupMethod,
        stepupCode,
      );
      setBatchDeleteOpen(false);
      setSelected(new Set());
      await load(query, statusFilter, roleFilter);
      toast.success(result.message);
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "批量删除失败";
        if (message.includes("当前密码") || message.includes("二次验证")) {
          setBatchDeleteError(message);
        } else {
          toast.error(message);
        }
      },
    },
  );

  const batchInviteAction = useAsyncAction(
    async (emails: string[]) => {
      const result = await adminUsersApi.batchInvite(emails);
      setBatchInviteOpen(false);
      setBatchInviteText("");
      await load(query, statusFilter, roleFilter);
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
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "批量邀请失败"),
    },
  );

  async function submitBatchInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const emails = batchInviteText
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (emails.length === 0) {
      toast.error("请至少填写一个邮箱");
      return;
    }
    await batchInviteAction.run(emails);
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          用户管理
          <span className="ml-2 text-sm font-normal text-muted">
            共 <AnimatedNumber value={users.length} /> 个账号
          </span>
        </h2>
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
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setSelected(new Set());
              load(query, e.target.value, roleFilter);
            }}
            className="input-sm sm:w-36"
            aria-label="按状态筛选"
          >
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setSelected(new Set());
              load(query, statusFilter, e.target.value);
            }}
            className="input-sm sm:w-32"
            aria-label="按角色筛选"
          >
            <option value="">全部角色</option>
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
          </select>
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
          <AsyncButton
            type="button"
            status={refreshAction.status}
            onClick={() => void refreshAction.run()}
            className="btn btn-secondary"
          >
            刷新
          </AsyncButton>
        </div>
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary-soft px-4 py-2">
          <span className="text-sm font-medium text-foreground">
            已选 {selected.size} 个账号
          </span>
          <AsyncButton
            type="button"
            status={batchStatusAction.pending ? "pending" : "idle"}
            onClick={() => void runBatchStatus("active")}
            disabled={selected.size === 0}
            className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
          >
            批量启用
          </AsyncButton>
          <AsyncButton
            type="button"
            status={batchStatusAction.pending ? "pending" : "idle"}
            onClick={() => void runBatchStatus("disabled")}
            disabled={selected.size === 0}
            className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
          >
            批量禁用
          </AsyncButton>
          <button
            onClick={() => {
              setBatchDeleteError(null);
              setAdminTwofa(null);
              twofaApi
                .status()
                .then(setAdminTwofa)
                .catch(() => setAdminTwofa(null));
              setBatchDeleteOpen(true);
            }}
            disabled={batchStatusAction.pending || batchDeleteAction.pending}
            className="btn btn-danger min-h-9 px-3 py-1.5 text-xs"
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

      <div className={`table-shell ${usersBreathing ? "animate-breath" : ""}`}>
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
                  ) : user.status === "cancelled" || user.status === "used" ? (
                    <span
                      className="badge badge-muted"
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
                    <div className="flex justify-end gap-1.5">
                      {(user.status === "invited" || user.status === "expired") && (
                        <button
                          onClick={() => startCancelInvite(user)}
                          disabled={inviteBusyId !== null}
                          className="btn btn-danger min-h-9 px-3 py-1.5 text-xs"
                        >
                          取消邀请
                        </button>
                      )}
                      <AsyncButton
                        type="button"
                        status={inviteBusyId === user.id ? "pending" : "idle"}
                        disabled={inviteBusyId !== null}
                        className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
                        onClick={() => void runResendInvite(user)}
                      >
                        重发邀请
                      </AsyncButton>
                      <button
                        onClick={() => startRemoveInvite(user)}
                        disabled={inviteBusyId !== null}
                        className="btn btn-danger min-h-9 px-3 py-1.5 text-xs"
                      >
                        删除
                      </button>
                    </div>
                  ) : (
                    <div className="flex justify-end gap-1.5">
                      <button
                        onClick={() => toggleStatus(user)}
                        disabled={user.id === currentAdminId}
                        title={user.id === currentAdminId ? "不能禁用自己" : undefined}
                        className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
                      >
                        {user.status === "active" ? "禁用" : "启用"}
                      </button>
                      <button
                        onClick={() => startResetPassword(user)}
                        className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
                      >
                        重置密码
                      </button>
                      <button
                        onClick={() => startReset2fa(user)}
                        className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
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
                        className="btn btn-danger min-h-9 px-3 py-1.5 text-xs"
                      >
                        删除
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="py-10 text-center text-sm text-muted"
                >
                  没有符合筛选条件的用户或邀请
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmTarget !== null}
        title={
          confirmTarget?.action === "toggle"
            ? "禁用/启用用户"
            : confirmTarget?.action === "cancelInvite"
              ? "取消邀请"
              : confirmTarget?.action === "removeInvite"
                ? "删除邀请记录"
                : "重置 2FA"
        }
        message={
          confirmTarget && (
            <span>
              {confirmTarget.action === "cancelInvite" ? (
                <>
                  确定取消 {confirmTarget.user.email} 的邀请吗？
                  取消后原邀请链接立即失效。
                </>
              ) : confirmTarget.action === "removeInvite" ? (
                <>
                  确定删除 {confirmTarget.user.email} 的邀请记录吗？
                  删除后原邀请链接立即失效，此操作不可恢复。
                </>
              ) : (
                <>
                  确定
                  {confirmTarget.action === "toggle" ? "禁用/启用" : "重置 2FA"}
                  用户 {confirmTarget.user.email} 吗？
                </>
              )}
            </span>
          )
        }
        intent="warning"
        confirmLabel={
          confirmTarget?.action === "toggle"
            ? "确认"
            : confirmTarget?.action === "cancelInvite"
              ? "确认取消"
              : confirmTarget?.action === "removeInvite"
                ? "确认删除"
                : "确认重置"
        }
        status={confirmAction.status}
        onConfirm={runConfirm}
        onCancel={() => setConfirmTarget(null)}
      >
        {confirmTarget?.action === "reset2fa" && (
          <label className="mt-3 block">
            <span className="label">管理员当前密码</span>
            <PasswordInput
              value={adminPassword}
              onChange={(e) => {
                setAdminPassword(e.target.value);
                setConfirmPasswordError(null);
              }}
              className="input"
              autoComplete="current-password"
              autoFocus
              required={!stepUp.active}
              aria-invalid={confirmPasswordError ? true : undefined}
              aria-describedby={
                confirmPasswordError ? "confirm-password-error" : undefined
              }
            />
            {stepUp.active && stepUp.status && (
              <StepUpNotice
                expiresInSeconds={stepUp.status.expires_in_seconds}
              />
            )}
            {confirmPasswordError && (
              <p
                id="confirm-password-error"
                role="alert"
                className="mt-1.5 text-xs text-destructive"
              >
                {confirmPasswordError}
              </p>
            )}
          </label>
        )}
      </ConfirmDialog>

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
              disabled={resetPasswordAction.pending}
            >
              取消
            </button>
            <AsyncButton
              type="submit"
              form="reset-password-form"
              status={resetPasswordAction.status}
              className="btn btn-primary"
            >
              确认重置
            </AsyncButton>
          </>
        }
      >
        <form
          id="reset-password-form"
          onSubmit={submitResetPassword}
          className="space-y-3"
        >
          <label className="block">
            <span className="label">管理员当前密码</span>
            <PasswordInput
              value={adminPassword}
              onChange={(e) => {
                setAdminPassword(e.target.value);
                setResetPasswordError(null);
              }}
              className="input"
              autoComplete="current-password"
              autoFocus
              required={!stepUp.active}
              aria-invalid={resetPasswordError ? true : undefined}
              aria-describedby={
                resetPasswordError ? "reset-password-error" : undefined
              }
            />
            {stepUp.active && stepUp.status && (
              <StepUpNotice
                expiresInSeconds={stepUp.status.expires_in_seconds}
              />
            )}
            {resetPasswordError && (
              <p
                id="reset-password-error"
                role="alert"
                className="mt-1.5 text-xs text-destructive"
              >
                {resetPasswordError}
              </p>
            )}
          </label>
          <label className="block">
            <span className="label">新密码</span>
            <PasswordInput
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
          if (!deleteAction.pending) setDeleteTarget(null);
        }}
        title={deleteTarget ? `删除账号：${deleteTarget.email}` : "删除账号"}
        intent="danger"
        footer={
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setDeleteTarget(null)}
            disabled={deleteAction.pending}
          >
            取消
          </button>
        }
      >
        <div className="space-y-3">
          <p className="text-foreground">
            删除后将永久移除该用户的会话、授权记录、恢复码与头像等全部数据，
            此操作不可恢复。
          </p>
          <StepUp2faForm
            emailOtpEnabled={adminTwofa?.email_otp_enabled === true}
            totpEnabled={adminTwofa?.totp_enabled === true}
            submitLabel="永久删除"
            status={deleteAction.status}
            serverError={deletePasswordError}
            onSubmit={({ current_password, stepup_method, stepup_code }) => {
              if (deleteTarget) {
                void deleteAction.run(
                  deleteTarget.id,
                  current_password,
                  stepup_method,
                  stepup_code,
                );
              }
            }}
          />
        </div>
      </Modal>

      <Modal
        open={createOpen}
        onClose={() => {
          if (!createAction.pending) setCreateOpen(false);
        }}
        title="添加账号"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setCreateOpen(false)}
              disabled={createAction.pending}
            >
              取消
            </button>
            <AsyncButton
              type="submit"
              form="create-user-form"
              status={createAction.status}
              className="btn btn-primary"
            >
              创建账号
            </AsyncButton>
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
            <PasswordInput
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
          if (!inviteAction.pending) setInviteOpen(false);
        }}
        title="邀请注册"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setInviteOpen(false)}
              disabled={inviteAction.pending}
            >
              取消
            </button>
            <AsyncButton
              type="submit"
              form="invite-user-form"
              status={inviteAction.status}
              className="btn btn-primary"
            >
              发送邀请
            </AsyncButton>
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
          if (!batchDeleteAction.pending) setBatchDeleteOpen(false);
        }}
        title="批量删除账号"
        intent="danger"
        footer={
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setBatchDeleteOpen(false)}
            disabled={batchDeleteAction.pending}
          >
            取消
          </button>
        }
      >
        <div className="space-y-3">
          <p className="text-foreground">
            将永久删除选中的 {selected.size} 个账号及其会话、授权记录、恢复码与头像等全部数据，
            此操作不可恢复。
          </p>
          <StepUp2faForm
            emailOtpEnabled={adminTwofa?.email_otp_enabled === true}
            totpEnabled={adminTwofa?.totp_enabled === true}
            submitLabel="永久删除"
            status={batchDeleteAction.status}
            serverError={batchDeleteError}
            onSubmit={({ current_password, stepup_method, stepup_code }) =>
              void batchDeleteAction.run(
                Array.from(selected),
                current_password,
                stepup_method,
                stepup_code,
              )
            }
          />
        </div>
      </Modal>

      <Modal
        open={batchInviteOpen}
        onClose={() => {
          if (!batchInviteAction.pending) setBatchInviteOpen(false);
        }}
        title="批量邀请注册"
        intent="info"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setBatchInviteOpen(false)}
              disabled={batchInviteAction.pending}
            >
              取消
            </button>
            <AsyncButton
              type="submit"
              form="batch-invite-user-form"
              status={batchInviteAction.status}
              className="btn btn-primary"
            >
              发送邀请
            </AsyncButton>
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
