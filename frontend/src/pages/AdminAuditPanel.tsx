import { useCallback, useEffect, useState } from "react";

import type { AuditLogOut } from "../api/types";
import { adminAuditApi } from "../api/client";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { AsyncButton } from "../components/AsyncButton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useBreathOnChange } from "../hooks/useBreathOnChange";
import { useToast } from "../hooks/useToast";

const CATEGORY_LABELS: Record<string, string> = {
  auth: "认证",
  user: "用户中心",
  "2fa": "二次验证",
  consent: "授权确认",
  oidc: "OIDC",
  admin_user: "用户管理",
  admin_client: "应用管理",
  admin_block: "黑名单",
  admin_settings: "站点设置",
  admin_notification: "通知管理",
  security: "安全",
  other: "其他",
};

const CATEGORIES = Object.keys(CATEGORY_LABELS);

export function AdminAuditPanel() {
  const [logs, setLogs] = useState<AuditLogOut[]>([]);
  const [category, setCategory] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const toast = useToast();
  const logsBreathing = useBreathOnChange(logs);

  const load = useCallback(
    (nextOffset = 0, append = false) => {
      adminAuditApi
        .list({
          category: category || undefined,
          action: actionFilter || undefined,
          offset: nextOffset,
          limit: 100,
        })
        .then((items) => {
          setLogs((prev) => (append ? [...prev, ...items] : items));
          setOffset(nextOffset + items.length);
          setHasMore(items.length === 100);
        })
        .catch((err) =>
          toast.error(err instanceof Error ? err.message : "加载失败")
        );
    },
    [actionFilter, category, toast]
  );

  const refreshAction = useAsyncAction(
    async () => {
      await load(0, false);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "刷新失败"),
    },
  );

  useEffect(() => {
    load(0, false);
  }, [load]);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          审计日志
          <span className="ml-2 text-sm font-normal text-muted">
            共 <AnimatedNumber value={logs.length} /> 条记录
          </span>
        </h2>
        <AsyncButton
          type="button"
          status={refreshAction.status}
          onClick={() => void refreshAction.run()}
          className="btn btn-secondary"
        >
          刷新
        </AsyncButton>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-foreground">
          <span>审计分类</span>
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setOffset(0);
              setHasMore(true);
            }}
            className="input-sm sm:w-40"
            aria-label="审计分类"
          >
            <option value="">全部</option>
            {CATEGORIES.map((key) => (
              <option key={key} value={key}>
                {CATEGORY_LABELS[key]}
              </option>
            ))}
          </select>
        </label>
        <input
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setOffset(0);
            setHasMore(true);
          }}
          placeholder="输入完整动作名"
          aria-label="审计动作"
          className="input-sm sm:w-64"
        />
      </div>

      <div className={`table-shell ${logsBreathing ? "animate-breath" : ""}`}>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>分类</th>
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
                  <span className="badge badge-muted">
                    {CATEGORY_LABELS[log.category ?? "other"] ??
                      log.category ??
                      "其他"}
                  </span>
                </td>
                <td>
                  {log.actor_type}:{log.actor_id ?? "-"}
                </td>
                <td>
                  <span className="badge badge-muted">{log.action}</span>
                </td>
                <td>
                  <div>{log.ip ?? "-"}</div>
                  {log.ip_location && (
                    <div className="text-xs text-muted">
                      {log.ip_location}
                    </div>
                  )}
                </td>
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
      {logs.length === 0 && (
        <p className="text-sm text-muted">
          暂无审计记录，登录与管理操作会在此留痕。
        </p>
      )}
      {hasMore && logs.length > 0 && (
        <button
          type="button"
          className="btn btn-secondary w-full"
          onClick={() => load(offset, true)}
        >
          加载更多
        </button>
      )}
    </section>
  );
}
