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

export function AdminSessionsPanel() {
  const [sessions, setSessions] = useState<AdminSessionOut[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [revokeTarget, setRevokeTarget] = useState<AdminSessionOut | null>(
    null,
  );
  const toast = useToast();
  const sessionsBreathing = useBreathOnChange(sessions);

  const load = useCallback(
    (q = "", offset = 0, append = false) => {
      return adminSessionsApi
        .list(q, offset, PAGE_SIZE)
        .then(({ items, total: nextTotal }) => {
          setSessions((prev) => (append ? [...prev, ...items] : items));
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
        </div>
      </div>

      <div className={`table-shell ${sessionsBreathing ? "animate-breath" : ""}`}>
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>设备</th>
              <th>IP</th>
              <th>认证方式</th>
              <th>最近活动</th>
              <th>登录时间</th>
              <th className="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id}>
                <td>
                  <div>{session.user.email}</div>
                  <div className="text-xs text-muted">
                    {session.user.nickname || "—"}
                  </div>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <span className="max-w-[12rem] truncate">
                      {session.device_name || "未知设备"}
                    </span>
                    {session.current && (
                      <span className="badge badge-primary">当前</span>
                    )}
                  </div>
                  <div
                    className="max-w-[16rem] truncate text-xs text-muted"
                    title={session.user_agent}
                  >
                    {session.user_agent || "—"}
                  </div>
                </td>
                <td className="whitespace-nowrap">{session.ip || "—"}</td>
                <td>
                  <span className="badge badge-muted">
                    {AUTH_METHOD_LABEL[session.auth_method] ?? session.auth_method}
                  </span>
                </td>
                <td className="whitespace-nowrap">
                  {new Date(session.last_used_at).toLocaleString()}
                </td>
                <td className="whitespace-nowrap">
                  {new Date(session.created_at).toLocaleString()}
                </td>
                <td className="text-right">
                  <button
                    type="button"
                    onClick={() => setRevokeTarget(session)}
                    disabled={session.current}
                    title={session.current ? "这是你当前的会话" : undefined}
                    className="btn btn-danger px-2.5 py-1.5 text-xs"
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
        <p className="text-sm text-muted">暂无在线会话</p>
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
    </section>
  );
}
