import { useCallback, useEffect, useState } from "react";

import { adminNotificationsApi, adminUsersApi } from "../api/client";
import type { AdminNotificationOut, AdminUserOut } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function AdminNotificationsPanel() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [inSite, setInSite] = useState(true);
  const [email, setEmail] = useState(false);
  const [scope, setScope] = useState<"all" | "specific">("all");
  const [userQuery, setUserQuery] = useState("");
  const [availableUsers, setAvailableUsers] = useState<AdminUserOut[]>([]);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(
    new Set()
  );
  const [usersLoading, setUsersLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [history, setHistory] = useState<AdminNotificationOut[]>([]);
  const [total, setTotal] = useState(0);
  const toast = useToast();

  const load = useCallback(
    (offset = 0, append = false) =>
      adminNotificationsApi
        .list(offset, 100)
        .then(({ items, total: nextTotal }) => {
          setHistory((prev) => (append ? [...prev, ...items] : items));
          setTotal(nextTotal);
        })
        .catch((err) =>
          toast.error(err instanceof Error ? err.message : "加载失败")
        ),
    [toast]
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (scope !== "specific") return;
    let cancelled = false;
    setUsersLoading(true);
    adminUsersApi
      .list("", "active", "")
      .then((items) => {
        if (!cancelled) {
          setAvailableUsers(
            items.filter((user) => user.kind === "user")
          );
        }
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载用户失败")
      )
      .finally(() => {
        if (!cancelled) setUsersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, toast]);

  const filteredUsers = availableUsers.filter((user) => {
    const query = userQuery.trim().toLowerCase();
    if (!query) return true;
    return (
      user.email.toLowerCase().includes(query) ||
      (user.nickname ?? "").toLowerCase().includes(query)
    );
  });

  function toggleUser(id: string) {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  const sendAction = useAsyncAction(
    async () => {
      const userIds =
        scope === "specific" ? Array.from(selectedUserIds) : undefined;
      const result = await adminNotificationsApi.create({
        title: title.trim(),
        body: body.trim(),
        in_site: inSite,
        email,
        ...(userIds ? { user_ids: userIds } : {}),
      });
      setTitle("");
      setBody("");
      setSelectedUserIds(new Set());
      setUserQuery("");
      await load();
      toast.success(
        `已发送给 ${result.recipient_count} 人${
          result.skipped ? `，跳过 ${result.skipped} 人` : ""
        }，邮件成功 ${result.email_sent} 封`
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "发送失败"),
    }
  );

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inSite && !email) {
      setFormError("至少选择一种发送渠道");
      return;
    }
    if (!title.trim() || !body.trim()) {
      setFormError("标题和正文不能为空");
      return;
    }
    const invalidTokens = [
      ...title.matchAll(/\{([^{}]+)\}/g),
      ...body.matchAll(/\{([^{}]+)\}/g),
    ]
      .map((match) => match[1])
      .filter((token) => token !== "nickname" && token !== "email");
    if (invalidTokens.length > 0) {
      setFormError(
        `不支持的占位符：${[...new Set(invalidTokens)]
          .map((token) => `{${token}}`)
          .join("、")}，仅支持 {nickname}、{email}`
      );
      return;
    }
    if (scope === "specific") {
      if (selectedUserIds.size === 0) {
        setFormError("请选择收件人");
        return;
      }
    }
    setFormError(null);
    void sendAction.run();
  }

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">通知管理</h2>
      <form onSubmit={submit} className="card space-y-4 p-6">
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">发送渠道</span>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={inSite}
              onChange={(event) => setInSite(event.target.checked)}
            />
            站内信
          </label>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={email}
              onChange={(event) => setEmail(event.target.checked)}
            />
            邮件（关闭邮件通知的用户自动跳过）
          </label>
        </div>
        <div className="space-y-2">
          <span className="text-sm font-medium text-foreground">收件人</span>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="scope"
              checked={scope === "all"}
              onChange={() => setScope("all")}
            />
            全部用户
          </label>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="radio"
              name="scope"
              checked={scope === "specific"}
              onChange={() => setScope("specific")}
            />
            指定用户
          </label>
          {scope === "specific" && (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <input
                aria-label="搜索用户"
                value={userQuery}
                onChange={(event) => setUserQuery(event.target.value)}
                placeholder="按邮箱或昵称搜索"
                className="input-sm w-full"
              />
              <div className="max-h-48 overflow-y-auto rounded-lg border border-border">
                {usersLoading ? (
                  <p className="p-3 text-sm text-muted">加载中…</p>
                ) : filteredUsers.length === 0 ? (
                  <p className="p-3 text-sm text-muted">
                    没有可选择的已注册用户
                  </p>
                ) : (
                  filteredUsers.map((user) => (
                    <label
                      key={user.id}
                      className="flex items-center gap-2 border-b border-border/50 px-3 py-2 text-sm text-foreground last:border-b-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedUserIds.has(user.id)}
                        onChange={() => toggleUser(user.id)}
                        aria-label={`选择 ${user.email}`}
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {user.email}
                      </span>
                      {user.nickname && (
                        <span className="truncate text-xs text-muted">
                          {user.nickname}
                        </span>
                      )}
                    </label>
                  ))
                )}
              </div>
              <p className="text-xs text-muted">
                已选 {selectedUserIds.size} 人
              </p>
            </div>
          )}
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">
            标题
            <input
              aria-label="标题"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={120}
              placeholder="例如：平台维护通知"
              className="input mt-1 w-full"
            />
          </label>
          <label className="block text-sm font-medium text-foreground">
            正文
            <textarea
              aria-label="正文"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              maxLength={5000}
              rows={5}
              placeholder={"支持占位符：{nickname} 昵称、{email} 邮箱"}
              className="input mt-1 w-full"
            />
          </label>
        </div>
        {formError && (
          <p className="text-sm text-destructive">{formError}</p>
        )}
        <AsyncButton
          type="submit"
          status={sendAction.status}
          className="btn btn-primary"
        >
          发送通知
        </AsyncButton>
      </form>

      <div className="table-shell">
        <table className="w-full">
          <thead>
            <tr>
              <th className="whitespace-nowrap">时间</th>
              <th className="whitespace-nowrap">标题</th>
              <th className="whitespace-nowrap">渠道</th>
              <th className="whitespace-nowrap">收件人</th>
              <th className="whitespace-nowrap">邮件</th>
              <th className="whitespace-nowrap">发送人</th>
            </tr>
          </thead>
          <tbody>
            {history.map((item) => (
              <tr key={item.id}>
                <td className="whitespace-nowrap">
                  {formatTime(item.created_at)}
                </td>
                <td className="max-w-[16rem] truncate">{item.title}</td>
                <td>
                  <span className="badge badge-muted">
                    {item.in_site ? "站内信" : "邮件"}
                  </span>
                  {item.in_site && item.email && (
                    <span className="ml-1 badge badge-muted">邮件</span>
                  )}
                </td>
                <td>{item.recipient_count} 人</td>
                <td>
                  {item.email
                    ? `成功 ${item.email_sent} / 失败 ${item.email_failed}`
                    : "—"}
                </td>
                <td className="truncate">{item.sender_email || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {history.length < total && (
          <button
            type="button"
            className="btn btn-secondary w-full"
            onClick={() => void load(history.length, true)}
          >
            加载更多
          </button>
        )}
      </div>
      {total === 0 && (
        <p className="text-sm text-muted">还没有发送记录。</p>
      )}
    </section>
  );
}
