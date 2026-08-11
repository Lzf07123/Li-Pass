import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { consentApi } from "../api/client";
import type { ConsentInfo } from "../api/types";

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
            <p>
              <strong>{info.client.name}</strong> 想获取以下权限：
            </p>
            <ul className="list-disc pl-6">
              {info.scopes.map((scope) => (
                <li key={scope}>{scope}</li>
              ))}
            </ul>
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
