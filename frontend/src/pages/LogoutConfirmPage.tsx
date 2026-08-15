import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { oauthApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { LineIcon } from "../components/bits/LineIcon";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";
import { APP_NAME } from "../lib/brand";

export function LogoutConfirmPage() {
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get("request_id") ?? "";
  const [clientName, setClientName] = useState("");
  const [error, setError] = useState("");
  const toast = useToast();

  useEffect(() => {
    if (!requestId) {
      setError("缺少登出请求参数");
      return;
    }
    oauthApi
      .logoutRequestInfo(requestId)
      .then((info) => setClientName(info.client_name))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "加载失败")
      );
  }, [requestId]);

  const decideAction = useAsyncAction(
    async (confirm: boolean) => {
      const result = confirm
        ? await oauthApi.confirmLogoutRequest(requestId)
        : await oauthApi.cancelLogoutRequest(requestId);
      window.location.href = result.redirect_url;
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    },
  );

  return (
    <AuthShell
      title="退出登录"
      subtitle="确认退出 SSO 与已登录的授权网站"
      ambientShapeCount={4}
    >
      {clientName ? (
        <div className="animate-fade-up space-y-4">
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 p-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-lg font-bold text-primary">
              {clientName.slice(0, 1).toUpperCase()}
            </span>
            <p className="min-w-0 truncate font-semibold text-foreground">
              {clientName}
            </p>
          </div>
          <p className="text-sm text-foreground">
            确认后，你将退出 {APP_NAME} 以及所有通过门户登录的授权网站。
          </p>
          <ul className="space-y-1.5 rounded-xl border border-border bg-surface-2/60 p-4 text-sm">
            <li className="flex items-center gap-1.5 text-foreground">
              <LineIcon name="check" className="h-4 w-4 shrink-0 text-primary" />
              <span>退出当前设备上的门户会话</span>
            </li>
            <li className="flex items-center gap-1.5 text-foreground">
              <LineIcon name="check" className="h-4 w-4 shrink-0 text-primary" />
              <span>通知已登录的授权网站一并退出</span>
            </li>
          </ul>
          <div className="flex gap-3">
            <AsyncButton
              type="button"
              status={decideAction.status}
              onClick={() => void decideAction.run(true)}
              className="btn btn-danger flex-1"
            >
              确认退出
            </AsyncButton>
            <AsyncButton
              type="button"
              status={decideAction.status}
              onClick={() => void decideAction.run(false)}
              className="btn btn-secondary flex-1"
            >
              取消
            </AsyncButton>
          </div>
        </div>
      ) : error ? (
        <Notice intent="error">{error}</Notice>
      ) : (
        <div
          className="animate-fade-up space-y-4"
          aria-busy="true"
          aria-label="正在加载登出信息"
        >
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 p-4">
            <div className="shimmer h-11 w-11 shrink-0 rounded-lg" />
            <div className="shimmer h-4 w-2/5 rounded" />
          </div>
          <div className="shimmer h-4 w-full rounded" />
          <div className="shimmer h-24 w-full rounded-xl" />
          <div className="flex gap-3">
            <div className="shimmer h-11 flex-1 rounded-lg" />
            <div className="shimmer h-11 flex-1 rounded-lg" />
          </div>
        </div>
      )}
    </AuthShell>
  );
}
