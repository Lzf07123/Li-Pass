import { useEffect } from "react";

import { meApi } from "../api/client";
import type { SessionInfo } from "../api/types";
import { useToast } from "./useToast";

const WARNING_THRESHOLD_MS = 5 * 60 * 1000;
const TICK_INTERVAL_MS = 15_000;
const RESYNC_THROTTLE_MS = 30_000;

/**
 * 会话空闲守护（前端侧兜底）：基于 /me 返回的会话生命周期做倒计时，
 * 剩余 5 分钟提示一次；倒计时归零派发 lipass:unauthorized 走全局跳转。
 * 用户活动时按 30 秒节流重新拉取 /me/session 同步服务端 last_used_at。
 */
export function useSessionIdle(session: SessionInfo | undefined): void {
  const toast = useToast();

  useEffect(() => {
    if (!session) return;
    const deadlineRef = {
      current: Date.now() + session.idle_remaining_seconds * 1000,
    };
    let warned = false;
    let lastResync = 0;

    const tick = () => {
      const remaining = deadlineRef.current - Date.now();
      if (remaining <= 0) {
        window.dispatchEvent(new Event("lipass:unauthorized"));
        return;
      }
      if (remaining <= WARNING_THRESHOLD_MS && !warned) {
        warned = true;
        toast.warning(
          "登录状态即将因长时间未操作过期，请继续操作或重新登录",
          { duration: 8000 },
        );
      }
    };

    const resync = () => {
      const now = Date.now();
      if (now - lastResync < RESYNC_THROTTLE_MS) return;
      lastResync = now;
      meApi
        .sessionInfo()
        .then((info) => {
          deadlineRef.current = Date.now() + info.idle_remaining_seconds * 1000;
        })
        .catch(() => undefined);
    };

    tick();
    const interval = window.setInterval(tick, TICK_INTERVAL_MS);
    window.addEventListener("pointerdown", resync);
    window.addEventListener("keydown", resync);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("pointerdown", resync);
      window.removeEventListener("keydown", resync);
    };
  }, [session, toast]);
}
