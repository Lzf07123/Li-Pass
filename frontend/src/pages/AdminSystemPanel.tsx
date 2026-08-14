import { useCallback, useEffect, useState } from "react";

import { adminSystemApi } from "../api/client";
import type { AdminSystemInfo } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

const ENVIRONMENT_LABEL: Record<string, string> = {
  development: "开发环境",
  testing: "测试环境",
  production: "生产环境",
};

const SERVICE_STATUS: Record<
  string,
  { label: string; dotClass: string; textClass: string }
> = {
  ok: { label: "正常", dotClass: "bg-success", textClass: "text-success" },
  error: {
    label: "异常",
    dotClass: "bg-destructive",
    textClass: "text-destructive",
  },
  unused: { label: "未使用", dotClass: "bg-border", textClass: "text-muted" },
};

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) {
    return "—";
  }
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value >= 100 || unit === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${BYTE_UNITS[unit]}`;
}

function formatDuration(seconds: number | null | undefined): string {
  if (
    seconds === null ||
    seconds === undefined ||
    !Number.isFinite(seconds) ||
    seconds < 0
  ) {
    return "—";
  }
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days} 天 ${hours} 小时`;
  if (hours > 0) return `${hours} 小时 ${minutes} 分`;
  return `${minutes} 分`;
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return value.toFixed(2);
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function meterClass(percent: number): string {
  if (percent >= 90) return "bg-destructive";
  if (percent >= 70) return "bg-warning";
  return "bg-success";
}

function Meter({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
      <div
        className={`h-full rounded-full ${meterClass(clamped)}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

function StatCard({
  title,
  value,
  hint,
  percent,
}: {
  title: string;
  value: string;
  hint?: string;
  percent?: number;
}) {
  return (
    <div className="card p-5">
      <p className="text-sm text-muted">{title}</p>
      <p className="mt-2 break-all text-2xl font-semibold text-foreground">
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
      {percent !== undefined ? (
        <div className="mt-3">
          <Meter percent={percent} />
        </div>
      ) : null}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="truncate text-right text-foreground" title={value}>
        {value}
      </span>
    </div>
  );
}

function ServiceRow({ label, status }: { label: string; status: string }) {
  const meta = SERVICE_STATUS[status] ?? SERVICE_STATUS.error;
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-muted">{label}</span>
      <span className={`flex items-center gap-2 ${meta.textClass}`}>
        <span
          className={`inline-block size-2 rounded-full ${meta.dotClass}`}
          aria-hidden="true"
        />
        {meta.label}
      </span>
    </div>
  );
}

export function AdminSystemPanel() {
  const [info, setInfo] = useState<AdminSystemInfo | null>(null);
  const toast = useToast();

  const load = useCallback(() => adminSystemApi.get().then(setInfo), []);

  useEffect(() => {
    void load().catch((err) =>
      toast.error(err instanceof Error ? err.message : "加载系统信息失败"),
    );
  }, [load, toast]);

  const refreshAction = useAsyncAction(
    async () => {
      await load();
      toast.success("系统信息已刷新");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "刷新失败"),
    },
  );

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-foreground">
          系统信息
          <span className="ml-2 text-sm font-normal text-muted">
            {info ? `采集于 ${formatTime(info.collected_at)}` : "加载中…"}
          </span>
        </h2>
        <AsyncButton
          type="button"
          status={refreshAction.status}
          disabled={info === null}
          className="btn btn-secondary"
          onClick={() => void refreshAction.run()}
        >
          刷新
        </AsyncButton>
      </div>

      {info ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="内存占用"
              value={`${info.memory.percent}%`}
              hint={`已用 ${formatBytes(info.memory.used_bytes)} / 共 ${formatBytes(info.memory.total_bytes)}`}
              percent={info.memory.percent}
            />
            <StatCard
              title="进程内存（RSS）"
              value={formatBytes(info.memory.process_rss_bytes)}
              hint={`进程 PID ${info.process.pid}`}
            />
            <StatCard
              title="磁盘使用"
              value={`${info.disk.percent}%`}
              hint={`已用 ${formatBytes(info.disk.used_bytes)} / 共 ${formatBytes(info.disk.total_bytes)}`}
              percent={info.disk.percent}
            />
            <StatCard
              title="进程运行时长"
              value={formatDuration(info.uptime.process_seconds)}
              hint={`系统已运行 ${formatDuration(info.uptime.system_seconds)}`}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="card p-5">
              <p className="text-sm text-muted">CPU 负载均值</p>
              <p className="mt-2 break-all text-2xl font-semibold text-foreground">
                {formatNumber(info.load.avg_1m)} / {formatNumber(info.load.avg_5m)} /{" "}
                {formatNumber(info.load.avg_15m)}
              </p>
              <p className="mt-1 text-xs text-muted">
                1 / 5 / 15 分钟 · {info.host.cpu_cores ?? "—"} 个 CPU 核心
              </p>
            </div>

            <div className="card p-5">
              <p className="mb-2 text-sm text-muted">运行环境</p>
              <InfoRow
                label="应用"
                value={`${info.app.name}（${ENVIRONMENT_LABEL[info.app.environment] ?? info.app.environment}）`}
              />
              <InfoRow
                label="Python"
                value={`${info.app.python_version}（${info.process.python_implementation}）`}
              />
              <InfoRow label="FastAPI" value={info.app.fastapi_version} />
              <InfoRow label="主机" value={info.host.hostname} />
              <InfoRow
                label="系统"
                value={`${info.host.system} ${info.host.release}（${info.host.machine}）`}
              />
            </div>

            <div className="card p-5">
              <p className="mb-2 text-sm text-muted">服务状态</p>
              <ServiceRow label="数据库" status={info.services.database} />
              <ServiceRow label="Redis" status={info.services.redis} />
            </div>
          </div>
        </div>
      ) : (
        <div className="card p-6 text-sm text-muted">正在获取系统信息…</div>
      )}
    </section>
  );
}
