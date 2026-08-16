import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { oauthApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
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

  const ssoLogoutAction = useAsyncAction(
    async () => {
      const result = await oauthApi.confirmLogoutRequest(requestId);
      window.location.href = result.redirect_url;
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    },
  );

  const localLogoutAction = useAsyncAction(
    async () => {
      const result = await oauthApi.localOnlyLogoutRequest(requestId);
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
      subtitle="请选择退出范围：仅当前网站，还是 SSO 与全部授权网站"
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
            退出登录有两种范围，请按需选择：
          </p>
          <div className="space-y-3">
            <div className="rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <p className="font-semibold text-foreground">登出 SSO</p>
                  <p className="text-sm text-muted">
                    退出 {APP_NAME} 登录，并通知所有通过门户登录的授权网站一并退出。
                  </p>
                </div>
                <AsyncButton
                  type="button"
                  status={ssoLogoutAction.status}
                  disabled={localLogoutAction.pending}
                  onClick={() => void ssoLogoutAction.run()}
                  className="btn btn-danger shrink-0"
                >
                  登出 SSO
                </AsyncButton>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface-2/60 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <p className="font-semibold text-foreground">仅登出本网站</p>
                  <p className="text-sm text-muted">
                    保留 {APP_NAME} 与其它网站的登录状态，仅返回「{clientName}」；当前网站的本地会话由该网站自行结束。
                  </p>
                </div>
                <AsyncButton
                  type="button"
                  status={localLogoutAction.status}
                  disabled={ssoLogoutAction.pending}
                  onClick={() => void localLogoutAction.run()}
                  className="btn btn-secondary shrink-0"
                >
                  仅登出本网站
                </AsyncButton>
              </div>
            </div>
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
