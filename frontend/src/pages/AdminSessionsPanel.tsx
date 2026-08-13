import { useCallback, useEffect, useState } from "react";

import { adminSessionsApi } from "../api/client";
import type { AdminSessionOut } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { AsyncButton } from "../components/AsyncButton";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useBreathOnChange } from "../hooks/useBreathOnChange";
import { useToast } from "../hooks/useToast";

const PAGE_SIZE = 100;

const AUTH_METHOD_LABEL: Record<string, string> = {
  password: "密码",
  email_otp: "邮箱验证码",
  totp: "TOTP",
};

/** 表格内紧凑时间：精确到分钟，秒级时间放在 title 提示中。 */
function formatSessionTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatFullTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN");
}

export function AdminSessionsPanel() {
  const [sessions, setSessions] = useState<AdminSessionOut[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchConfirmOpen, setBatchConfirmOpen] = useState(false);
  const [allConfirmOpen, setAllConfirmOpen] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<AdminSessionOut | null>(
    null,
  );
  const toast = useToast();
  const sessionsBreathing = useBreathOnChange(sessions);
  const selectable = sessions.filter((session) => !session.current);
  const allSelected =
    selectable.length > 0 &&
    selectable.every((session) => selected.has(session.id));

  const load = useCallback(
    (q = "", offset = 0, append = false) => {
      return adminSessionsApi
        .list(q, offset, PAGE_SIZE)
        .then(({ items, total: nextTotal }) => {
          setSessions((prev) => (append ? [...prev, ...items] : items));
          if (!append) setSelected(new Set());
          setTotal(nextTotal);
        })
        .catch((err) =>
          toast.error(err instanceof Error ? err.message : "加载失败"),
        );
    },
    [toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(query);
  }

  const hasMore = sessions.length < total;

  const refreshAction = useAsyncAction(
    async () => {
      await load(query);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "刷新失败"),
    },
  );

  const revokeAction = useAsyncAction(
    async (id: string) => {
      await adminSessionsApi.revoke(id);
      setRevokeTarget(null);
      await load(query);
      toast.success("会话已强制下线");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "下线失败"),
    },
  );

  function confirmRevoke() {
    if (!revokeTarget) return;
    void revokeAction.run(revokeTarget.id);
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
      setSelected(new Set(selectable.map((session) => session.id)));
    }
  }

  const batchRevokeAction = useAsyncAction(
    async (ids: string[]) => {
      const result = await adminSessionsApi.revokeMany(ids);
      setBatchConfirmOpen(false);
      setSelected(new Set());
      await load(query);
      toast.success(`已下线 ${result.revoked} 个会话`);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "批量下线失败"),
    },
  );

  function confirmBatchRevoke() {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    void batchRevokeAction.run(ids);
  }

  const revokeAllAction = useAsyncAction(
    async () => {
      const result = await adminSessionsApi.revokeAll();
      setAllConfirmOpen(false);
      setSelected(new Set());
      await load(query);
      toast.success(
        result.revoked > 0
          ? `已下线 ${result.revoked} 个会话`
          : "没有其他会话需要下线",
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "全部下线失败"),
    },
  );

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          会话监控
          <span className="ml-2 text-sm font-normal text-muted">
            共 <AnimatedNumber value={total} /> 个在线会话
          </span>
        </h2>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <form onSubmit={search} className="flex w-full gap-2 sm:w-auto">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="按邮箱、昵称、IP 或设备搜索"
              className="input sm:w-72"
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
          <AsyncButton
            type="button"
            status={revokeAllAction.status}
            onClick={() => setAllConfirmOpen(true)}
            disabled={total === 0}
            className="btn btn-danger"
          >
            全部下线
          </AsyncButton>
        </div>
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-primary/30 bg-primary-soft px-4 py-2">
          <span className="text-sm font-medium text-foreground">
            已选 {selected.size} 个会话
          </span>
          <button
            type="button"
            onClick={() => setBatchConfirmOpen(true)}
            disabled={batchRevokeAction.pending}
            className="btn btn-danger min-h-9 px-3 py-1.5 text-xs"
          >
            批量下线
          </button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            disabled={batchRevokeAction.pending}
            className="btn-link text-xs"
          >
            取消选择
          </button>
        </div>
      )}

      <div className={`table-shell ${sessionsBreathing ? "animate-breath" : ""}`}>
        <table className="w-full min-w-[60rem] table-fixed">
          <thead>
            <tr>
              <th className="w-10">
                <input
                  type="checkbox"
                  checked={allSelected}
                  disabled={selectable.length === 0}
                  onChange={toggleSelectAll}
                  aria-label="全选会话"
                />
              </th>
              <th className="w-[136px] whitespace-nowrap">用户</th>
              <th className="w-[184px] whitespace-nowrap">设备</th>
              <th className="w-[112px] whitespace-nowrap">IP</th>
              <th className="w-[104px] whitespace-nowrap">认证方式</th>
              <th className="w-[144px] whitespace-nowrap">最近活动</th>
              <th className="w-[144px] whitespace-nowrap">登录时间</th>
              <th className="w-[110px] whitespace-nowrap text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={selected.has(session.id)}
                    disabled={session.current}
                    onChange={() => toggleSelect(session.id)}
                    aria-label={`选择 ${session.user.email}`}
                  />
                </td>
                <td>
                  <div className="truncate" title={session.user.email}>
                    {session.user.email}
                  </div>
                  <div className="truncate text-xs text-muted">
                    {session.user.nickname || "—"}
                  </div>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <span className="max-w-[12rem] truncate">
                      {session.device_name || "未知设备"}
                    </span>
                    {session.current && (
                      <span className="badge badge-primary shrink-0">当前</span>
                    )}
                  </div>
                  <div
                    className="truncate text-xs text-muted"
                    title={session.user_agent}
                  >
                    {session.user_agent || "—"}
                  </div>
                </td>
                <td>
                  <div className="truncate" title={session.ip ?? undefined}>
                    {session.ip || "—"}
                  </div>
                </td>
                <td>
                  <span className="badge badge-muted">
                    {AUTH_METHOD_LABEL[session.auth_method] ?? session.auth_method}
                  </span>
                </td>
                <td
                  className="whitespace-nowrap"
                  title={formatFullTime(session.last_used_at)}
                >
                  {formatSessionTime(session.last_used_at)}
                </td>
                <td
                  className="whitespace-nowrap"
                  title={formatFullTime(session.created_at)}
                >
                  {formatSessionTime(session.created_at)}
                </td>
                <td className="text-right">
                  <button
                    type="button"
                    onClick={() => setRevokeTarget(session)}
                    disabled={session.current}
                    title={session.current ? "这是你当前的会话" : undefined}
                    className="btn btn-danger min-h-9 whitespace-nowrap px-3 py-1.5 text-xs"
                  >
                    强制下线
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {hasMore && (
          <button
            type="button"
            className="btn btn-secondary w-full"
            onClick={() => void load(query, sessions.length, true)}
          >
            加载更多
          </button>
        )}
      </div>
      {total === 0 && (
        <p className="text-sm text-muted">
          暂无在线会话，用户登录后会实时出现在这里。
        </p>
      )}

      <ConfirmDialog
        open={revokeTarget !== null}
        title="强制下线会话"
        intent="danger"
        confirmLabel="确认下线"
        status={revokeAction.status}
        onConfirm={confirmRevoke}
        onCancel={() => {
          if (!revokeAction.pending) setRevokeTarget(null);
        }}
      >
        {revokeTarget && (
          <span>
            确定强制下线 {revokeTarget.user.email} 在「
            {revokeTarget.device_name || "未知设备"}」的会话吗？该用户需要重新登录才能继续访问。
          </span>
        )}
      </ConfirmDialog>

      <ConfirmDialog
        open={batchConfirmOpen}
        title="批量下线会话"
        intent="danger"
        confirmLabel="确认下线"
        status={batchRevokeAction.status}
        onConfirm={confirmBatchRevoke}
        onCancel={() => {
          if (!batchRevokeAction.pending) setBatchConfirmOpen(false);
        }}
      >
        <span>
          将强制下线选中的 {selected.size} 个会话，相关用户需要重新登录。当前会话不受影响。
        </span>
      </ConfirmDialog>

      <ConfirmDialog
        open={allConfirmOpen}
        title="全部下线"
        intent="danger"
        confirmLabel="全部下线"
        status={revokeAllAction.status}
        onConfirm={() => void revokeAllAction.run()}
        onCancel={() => {
          if (!revokeAllAction.pending) setAllConfirmOpen(false);
        }}
      >
        <span>
          将强制下线除你当前会话外的全部在线会话（当前共 {total} 个在线会话），相关用户需要重新登录。
        </span>
      </ConfirmDialog>
    </section>
  );
}
