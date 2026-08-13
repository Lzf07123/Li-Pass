import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi, userMessagesApi } from "../api/client";
import type { MessageOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { FloatingBackground } from "../components/FloatingBackground";
import { PageSkeleton } from "../components/PageSkeleton";
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

export function MessagesPage() {
  const [ready, setReady] = useState(false);
  const [items, setItems] = useState<MessageOut[]>([]);
  const [unread, setUnread] = useState(0);
  const toast = useToast();
  const navigate = useNavigate();

  const load = useCallback(() => {
    userMessagesApi
      .list(0, 100)
      .then((data) => {
        setItems(data.items);
        setUnread(data.unread);
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败")
      );
  }, [toast]);

  useEffect(() => {
    authApi
      .me()
      .then(() => {
        setReady(true);
        load();
      })
      .catch(() => navigate("/login"));
  }, [load, navigate]);

  const markReadAction = useAsyncAction(
    async (id: string) => {
      await userMessagesApi.markRead(id);
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, read: true } : item))
      );
      setUnread((value) => Math.max(0, value - 1));
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    }
  );

  const markAllAction = useAsyncAction(
    async () => {
      const result = await userMessagesApi.markAllRead();
      setItems((prev) => prev.map((item) => ({ ...item, read: true })));
      setUnread(0);
      toast.success(`已将 ${result.updated} 条消息标记为已读`);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    }
  );

  const removeAction = useAsyncAction(
    async (id: string) => {
      await userMessagesApi.remove(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      toast.success("消息已删除");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "删除失败"),
    }
  );

  if (!ready) {
    return <PageSkeleton title="站内信" />;
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      <FloatingBackground
        theme="auto"
        transparent
        shapeCount={4}
        opacity={0.5}
      />
      <AppHeader
        title="站内信"
        actions={
          <Link to="/" className="btn btn-secondary">
            返回用户中心
          </Link>
        }
      />
      <main className="relative mx-auto w-full max-w-3xl flex-1 space-y-4 px-4 py-8 sm:px-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">未读 {unread} 条</p>
          {unread > 0 && (
            <button
              type="button"
              onClick={() => void markAllAction.run()}
              className="btn btn-secondary min-h-9 px-3 py-1.5 text-xs"
            >
              全部已读
            </button>
          )}
        </div>
        {items.length === 0 ? (
          <div className="card p-10 text-center text-sm text-muted">
            暂无站内信
          </div>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li
                key={item.id}
                className={`card space-y-2 p-4 ${
                  item.read ? "" : "border-primary/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-foreground">
                      {item.title}
                    </p>
                    <p className="text-xs text-muted">
                      {formatTime(item.sent_at)}
                    </p>
                  </div>
                  {!item.read && (
                    <span className="badge badge-primary">未读</span>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm text-foreground">
                  {item.body}
                </p>
                <div className="flex gap-2">
                  {!item.read && (
                    <button
                      type="button"
                      onClick={() => void markReadAction.run(item.id)}
                      className="btn-link text-xs"
                    >
                      标记已读
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void removeAction.run(item.id)}
                    className="btn-link text-xs text-destructive"
                  >
                    删除
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
