import { useEffect, useState } from "react";

import { adminAuditApi } from "../api/client";
import type { AuditLogOut } from "../api/types";

export function AdminAuditPanel() {
  const [logs, setLogs] = useState<AuditLogOut[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    adminAuditApi
      .list()
      .then(setLogs)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">审计日志</h2>
      {error && <p className="mb-2 rounded bg-red-50 p-2 text-red-700">{error}</p>}
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="p-2">时间</th>
            <th className="p-2">操作者</th>
            <th className="p-2">动作</th>
            <th className="p-2">IP</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
