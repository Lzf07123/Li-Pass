import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { authApi, consentApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { LineIcon } from "../components/bits/LineIcon";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";
import type { ConsentInfo } from "../api/types";

const SCOPE_LABELS: Record<string, string> = {
  openid: "OpenID 身份标识",
  profile: "昵称与头像等基本资料",
  email: "邮箱地址",
  phone: "手机号",
};

export function ConsentPage() {
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get("request_id") ?? "";
  const [info, setInfo] = useState<ConsentInfo | null>(null);
  const [error, setError] = useState("");
  const toast = useToast();

  useEffect(() => {
    if (!requestId) return;
    consentApi
      .info(requestId)
      .then(setInfo)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [requestId]);

  const decideAction = useAsyncAction(
    async (approve: boolean) => {
      const result = approve
        ? await consentApi.approve(requestId)
        : await consentApi.deny(requestId);
      window.location.href = result.redirect_url;
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    },
  );

  const switchAccountAction = useAsyncAction(
    async () => {
      await authApi.logoutLocal();
      const next = encodeURIComponent(`/consent?request_id=${requestId}`);
      window.location.href = `/login?next=${next}`;
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "操作失败"),
    },
  );

  function decide(approve: boolean) {
    void decideAction.run(approve);
  }

  return (
    <AuthShell
      title="授权确认"
      subtitle="请确认你要授权的网站与权限范围"
      ambientShapeCount={4}
    >
      {info ? (
        <div className="animate-fade-up space-y-4">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2/60 p-3 text-sm">
            <p className="min-w-0 truncate text-foreground">
              正在以 <strong className="font-semibold">{info.user.email}</strong> 登录
            </p>
            <AsyncButton
              type="button"
              status={switchAccountAction.status}
              onClick={() => void switchAccountAction.run()}
              className="btn btn-secondary shrink-0"
            >
              使用其他账号登录
            </AsyncButton>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 p-4">
            {info.client.logo_url ? (
              <img
                src={info.client.logo_url}
                alt={`${info.client.name} 图标`}
                className="h-11 w-11 rounded-lg object-contain"
              />
            ) : (
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-lg font-bold text-primary">
                {info.client.name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <div className="min-w-0">
              <p className="truncate font-semibold text-foreground">
                {info.client.name}
              </p>
              {info.client.description && (
                <p className="truncate text-sm text-muted">
                  {info.client.description}
                </p>
              )}
            </div>
          </div>

          <p className="text-sm text-foreground">
            <strong>{info.client.name}</strong> 想获取以下权限：
          </p>
          <ul className="space-y-1.5 rounded-xl border border-border bg-surface-2/60 p-4 text-sm">
            {info.scopes.map((scope) => (
              <li key={scope} className="flex items-center gap-1.5 text-foreground">
                <LineIcon name="check" className="h-4 w-4 shrink-0 text-primary" />
                <span>{SCOPE_LABELS[scope] ?? scope}</span>
                <span className="text-xs text-muted">（{scope}）</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            登录后将跳回 {info.client.name}，不会向对方泄露你的密码。
          </p>
          <div className="flex gap-3">
            <AsyncButton
              type="button"
              status={decideAction.status}
              onClick={() => decide(true)}
              className="btn btn-primary flex-1"
            >
              同意授权
            </AsyncButton>
            <AsyncButton
              type="button"
              status={decideAction.status}
              onClick={() => decide(false)}
              className="btn btn-secondary flex-1"
            >
              拒绝
            </AsyncButton>
          </div>
        </div>
      ) : error ? (
        <Notice intent="error">{error}</Notice>
      ) : (
        <div
          className="animate-fade-up space-y-4"
          aria-busy="true"
          aria-label="正在加载授权信息"
        >
          {/* 客户端信息卡片 */}
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 p-4">
            <div className="shimmer h-11 w-11 shrink-0 rounded-lg" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="shimmer h-4 w-2/5 rounded" />
              <div className="shimmer h-3.5 w-3/5 rounded" />
            </div>
          </div>

          <div className="shimmer h-4 w-52 rounded" />

          {/* 权限范围列表 */}
          <div className="space-y-3 rounded-xl border border-border bg-surface-2/60 p-4">
            <div className="shimmer h-4 w-3/4 rounded" />
            <div className="shimmer h-4 w-2/3 rounded" />
            <div className="shimmer h-4 w-5/6 rounded" />
          </div>

          <div className="shimmer h-3.5 w-64 rounded" />

          {/* 操作按钮 */}
          <div className="flex gap-3">
            <div className="shimmer h-11 flex-1 rounded-lg" />
            <div className="shimmer h-11 flex-1 rounded-lg" />
          </div>
        </div>
      )}
    </AuthShell>
  );
}
