import { useCallback, useEffect, useState } from "react";

import { adminNotificationsApi } from "../api/client";
import type { AdminNotificationOut } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
  const [emailsText, setEmailsText] = useState("");
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

  const sendAction = useAsyncAction(
    async () => {
      const emails =
        scope === "specific"
          ? emailsText
              .split(/[\n,，;；\s]+/)
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined;
      const result = await adminNotificationsApi.create({
        title: title.trim(),
        body: body.trim(),
        in_site: inSite,
        email,
        ...(emails ? { emails } : {}),
      });
      setTitle("");
      setBody("");
      setEmailsText("");
      await load();
      toast.success(
        `已发送给 ${result.recipient_count} 人，邮件成功 ${result.email_sent} 封`
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
    if (scope === "specific") {
      const emails = emailsText
        .split(/[\n,，;；\s]+/)
        .map((item) => item.trim())
        .filter(Boolean);
      if (emails.length === 0) {
        setFormError("请填写收件人邮箱");
        return;
      }
      const bad = emails.find((item) => !EMAIL_RE.test(item));
      if (bad) {
        setFormError(`邮箱格式不正确：${bad}`);
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
            <textarea
              aria-label="收件人邮箱（每行一个）"
              value={emailsText}
              onChange={(event) => setEmailsText(event.target.value)}
              placeholder={"每行一个邮箱，例如：\na@example.com\nb@example.com"}
              className="input min-h-24 w-full"
            />
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
