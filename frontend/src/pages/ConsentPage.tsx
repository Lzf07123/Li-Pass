import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { consentApi } from "../api/client";
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
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">授权确认</h1>
        {info ? (
          <>
            <div className="flex items-center gap-3">
              {info.client.logo_url ? (
                <img
                  src={info.client.logo_url}
                  alt={`${info.client.name} 图标`}
                  className="h-10 w-10 rounded object-contain"
                />
              ) : (
                <span className="flex h-10 w-10 items-center justify-center rounded bg-blue-100 text-lg font-bold text-blue-600">
                  {info.client.name.slice(0, 1).toUpperCase()}
                </span>
              )}
              <div>
                <p className="font-semibold">{info.client.name}</p>
                {info.client.description && (
                  <p className="text-sm text-gray-500">{info.client.description}</p>
                )}
              </div>
            </div>
            <p>
              <strong>{info.client.name}</strong> 想获取以下权限：
            </p>
            <ul className="space-y-1 rounded border bg-gray-50 p-3 text-sm">
              {info.scopes.map((scope) => (
                <li key={scope}>
                  {SCOPE_LABELS[scope] ?? scope}
                  <span className="ml-1 text-xs text-gray-400">（{scope}）</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-500">
              登录后将跳回 {info.client.name}，不会向对方泄露你的密码。
            </p>
            {error && <p className="text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => decide(true)}
                className="flex-1 rounded bg-blue-600 p-2 text-white"
              >
                同意授权
              </button>
              <button
                onClick={() => decide(false)}
                className="flex-1 rounded bg-gray-300 p-2"
              >
                拒绝
              </button>
            </div>
          </>
        ) : (
          <p>{error || "加载中…"}</p>
        )}
      </div>
    </main>
  );
}
