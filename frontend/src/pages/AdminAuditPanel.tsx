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
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">审计日志</h2>
        <button onClick={load} className="btn btn-secondary">
          刷新
        </button>
      </div>
      {error && (
        <p className="alert alert-error" role="alert">
          {error}
        </p>
      )}
      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>动作</th>
              <th>IP</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td className="whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td>
                  {log.actor_type}:{log.actor_id ?? "-"}
                </td>
                <td>
                  <span className="badge badge-muted">{log.action}</span>
                </td>
                <td>{log.ip ?? "-"}</td>
                <td>
                  {log.detail && Object.keys(log.detail).length > 0 ? (
                    <details>
                      <summary className="cursor-pointer text-primary">
                        查看
                      </summary>
                      <pre className="mt-1 max-h-32 overflow-auto rounded-lg bg-surface-2 p-2.5 text-xs text-foreground">
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
      </div>
      {logs.length === 0 && <p className="text-sm text-muted">暂无审计记录</p>}
    </section>
  );
}
