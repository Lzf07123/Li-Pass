import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { userMessagesApi } from "../api/client";
import { LineIcon } from "./bits/LineIcon";

export function MessageBell() {
  const [unread, setUnread] = useState<number | null>(null);

  const load = useCallback(() => {
    userMessagesApi
      .unreadCount()
      .then((data) => setUnread(data.unread))
      .catch(() => setUnread(null));
  }, []);

  useEffect(() => {
    let lastRefresh = 0;
    load();
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      const now = Date.now();
      if (now - lastRefresh < 500) return;
      lastRefresh = now;
      load();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [load]);

  if (unread === null) return null;
  return (
    <Link
      to="/messages"
      className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
      aria-label={unread > 0 ? `站内信，${unread} 条未读` : "站内信"}
    >
      <LineIcon name="mail" className="h-5 w-5" />
      {unread > 0 && (
        <span className="absolute right-0 top-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-white">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
