import { useCallback, useEffect, useState } from "react";

import { adminAuditApi } from "../api/client";
import type { AuditLogOut } from "../api/types";

export function AdminAuditPanel() {
  const [logs, setLogs] = useState<AuditLogOut[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    adminAuditApi
      .list()
      .then(setLogs)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">审计日志</h2>
        <button onClick={load} className="rounded bg-gray-200 p-2 text-sm">
          刷新
        </button>
      </div>
      {error && <p className="mb-2 rounded bg-red-50 p-2 text-red-700">{error}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="p-2">时间</th>
            <th className="p-2">操作者</th>
            <th className="p-2">动作</th>
            <th className="p-2">IP</th>
            <th className="p-2">详情</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-b">
              <td className="p-2">{new Date(log.created_at).toLocaleString()}</td>
              <td className="p-2">
                {log.actor_type}:{log.actor_id ?? "-"}
              </td>
              <td className="p-2">{log.action}</td>
              <td className="p-2">{log.ip ?? "-"}</td>
              <td className="p-2">
                {log.detail && Object.keys(log.detail).length > 0 ? (
                  <details>
                    <summary className="cursor-pointer text-blue-600">查看</summary>
                    <pre className="mt-1 max-h-32 overflow-auto rounded bg-gray-100 p-2 text-xs">
                      {JSON.stringify(log.detail, null, 2)}
                    </pre>
                  </details>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {logs.length === 0 && (
        <p className="mt-3 text-sm text-gray-500">暂无审计记录</p>
      )}
    </section>
  );
}
