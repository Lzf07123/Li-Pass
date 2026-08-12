import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { consentApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";
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

  useEffect(() => {
    if (!requestId) return;
    consentApi
      .info(requestId)
      .then(setInfo)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [requestId]);

  async function decide(approve: boolean) {
    setError("");
    try {
      const result = approve
        ? await consentApi.approve(requestId)
        : await consentApi.deny(requestId);
      window.location.href = result.redirect_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  return (
    <AuthShell title="授权确认" subtitle="请确认你要授权的网站与权限范围">
      {info ? (
        <div className="space-y-4">
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
              <li key={scope} className="flex items-baseline gap-1.5 text-foreground">
                <span className="text-primary">✓</span>
                <span>{SCOPE_LABELS[scope] ?? scope}</span>
                <span className="text-xs text-muted">（{scope}）</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            登录后将跳回 {info.client.name}，不会向对方泄露你的密码。
          </p>
          {error && (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          )}
          <div className="flex gap-3">
            <button
              onClick={() => decide(true)}
              className="btn btn-primary flex-1"
            >
              同意授权
            </button>
            <button
              onClick={() => decide(false)}
              className="btn btn-secondary flex-1"
            >
              拒绝
            </button>
          </div>
        </div>
      ) : (
        <p className="py-4 text-center text-sm text-muted">
          {error || "加载中…"}
        </p>
      )}
    </AuthShell>
  );
}
