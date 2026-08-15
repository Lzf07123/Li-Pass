import { useCallback, useState } from "react";

import { meApi } from "../api/client";
import type { StepUpStatus } from "../api/types";

const CACHE_TTL_MS = 30_000;

// 模块级缓存：同一 SPA 内各页面共享复核窗口状态，避免重复请求；
// 30 秒内的状态视为新鲜，主动 refresh 或复核失败时失效。
let cache: { status: StepUpStatus; at: number } | null = null;

/**
 * 敏感操作 step-up 复核窗口：窗口内免再次输入密码。
 * 后端为权威判定，本 hook 仅用于减少无效交互与展示提示。
 */
export function useStepUp() {
  const [status, setStatus] = useState<StepUpStatus | null>(
    cache ? cache.status : null,
  );
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async (force = false) => {
    if (!force && cache && Date.now() - cache.at < CACHE_TTL_MS) {
      setStatus(cache.status);
      return cache.status;
    }
    setLoading(true);
    try {
      const next = await meApi.stepUpStatus();
      cache = { status: next, at: Date.now() };
      setStatus(next);
      return next;
    } catch {
      cache = null;
      setStatus(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const verify = useCallback(async (password: string) => {
    const next = await meApi.stepUpVerify(password);
    cache = { status: next, at: Date.now() };
    setStatus(next);
    return next;
  }, []);

  const invalidate = useCallback(() => {
    cache = null;
    setStatus(null);
  }, []);

  return {
    status,
    active: status?.active === true,
    loading,
    refresh,
    verify,
    invalidate,
  };
}
