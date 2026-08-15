import { useCallback, useEffect, useState } from "react";

import { adminStatsApi } from "../api/client";
import type { AdminStats } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { MagicBento } from "../components/bits/MagicBento";
import { ChinaMap } from "../components/charts/ChinaMap";
import { LineChart } from "../components/charts/LineChart";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const RANGE_OPTIONS = [
  { days: 7, label: "近 7 天" },
  { days: 30, label: "近 30 天" },
  { days: 90, label: "近 90 天" },
] as const;

const AUTH_METHOD_LABEL: Record<string, string> = {
  password: "密码",
  email_otp: "邮箱验证码",
  totp: "TOTP",
  recovery: "恢复码",
};

const numberFormat = new Intl.NumberFormat("zh-CN");

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export function AdminStatsPanel() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [days, setDays] = useState(30);
  const toast = useToast();

  const load = useCallback(
    (rangeDays: number) => adminStatsApi.get(rangeDays).then(setStats),
    [],
  );

  useEffect(() => {
    void load(days).catch((err) =>
      toast.error(err instanceof Error ? err.message : "加载统计数据失败"),
    );
  }, [days, load, toast]);

  const refreshAction = useAsyncAction(
    async () => {
      await load(days);
      toast.success("统计数据已刷新");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "刷新失败"),
    },
  );

  const chartLabels = stats ? stats.daily.map((point) => point.date.slice(5)) : [];
  const chartSeries = stats
    ? [
        {
          name: "登录次数",
          values: stats.daily.map((point) => point.logins),
          color: "var(--portal-primary)",
        },
        {
          name: "登录人数",
          values: stats.daily.map((point) => point.login_users),
          color: "var(--portal-success)",
        },
        {
          name: "新增注册",
          values: stats.daily.map((point) => point.registrations),
          color: "var(--portal-warning)",
          dashed: true,
        },
      ]
    : [];

  const overviewCards = stats
    ? [
        {
          title: "账号总数",
          value: numberFormat.format(stats.overview.total_users),
          hint: `启用 ${numberFormat.format(stats.overview.active_users)} · 禁用 ${numberFormat.format(stats.overview.disabled_users)}`,
        },
        {
          title: "管理员",
          value: numberFormat.format(stats.overview.admins),
        },
        {
          title: "已验证邮箱",
          value: numberFormat.format(stats.overview.verified_users),
        },
        {
          title: "在线会话",
          value: numberFormat.format(stats.overview.online_sessions),
        },
        {
          title: "累计登录次数",
          value: numberFormat.format(stats.overview.total_logins),
        },
        {
          title: `新增注册（${days} 天）`,
          value: numberFormat.format(
            stats.daily.reduce((sum, point) => sum + point.registrations, 0),
          ),
        },
      ]
    : [];

  const totalSessions = stats
    ? stats.auth_methods.reduce((sum, item) => sum + item.count, 0)
    : 0;
  const maxMethodCount = stats
    ? Math.max(1, ...stats.auth_methods.map((item) => item.count))
    : 1;
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-foreground">
          数据统计
          {stats ? (
            <span className="ml-2 text-sm font-normal text-muted">
              统计截止 {formatTime(stats.generated_at)}
            </span>
          ) : (
            <span className="ml-2 text-sm font-normal text-muted">加载中…</span>
          )}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1" role="group" aria-label="统计时间范围">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.days}
                type="button"
                aria-pressed={days === option.days}
                onClick={() => setDays(option.days)}
                className={`btn px-3 py-2 ${
                  days === option.days ? "btn-primary" : "btn-secondary"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <AsyncButton
            type="button"
            status={refreshAction.status}
            disabled={stats === null}
            className="btn btn-secondary"
            onClick={() => void refreshAction.run()}
          >
            刷新
          </AsyncButton>
        </div>
      </div>

      {stats ? (
        <div className="space-y-4">
          <MagicBento
            items={overviewCards.map((card) => ({
              label: card.title,
              title: card.value,
              description: card.hint ?? "",
              emphasize: true,
            }))}
            textAutoHide={false}
            enableTilt
            particleCount={6}
            spotlightRadius={260}
            compact
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="card p-5 lg:col-span-2">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm text-muted">
                  登录与注册趋势（近 {days} 天）
                </p>
                <p className="text-xs text-muted">
                  按 Asia/Shanghai 自然日聚合
                </p>
              </div>
              <LineChart
                labels={chartLabels}
                series={chartSeries}
                formatValue={(value) => numberFormat.format(value)}
              />
            </div>

            <div className="card p-5">
              <p className="mb-3 text-sm text-muted">
                认证方式分布（在线会话）
              </p>
              {totalSessions === 0 ? (
                <p className="text-sm text-muted">暂无在线会话</p>
              ) : (
                <div className="space-y-2.5">
                  {stats.auth_methods.map((item) => (
                    <div
                      key={item.method}
                      className="flex items-center gap-3 text-sm"
                    >
                      <span className="w-20 shrink-0 text-muted">
                        {AUTH_METHOD_LABEL[item.method] ?? item.method}
                      </span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{
                            width: `${(item.count / maxMethodCount) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-right text-foreground">
                        {numberFormat.format(item.count)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="mt-3 text-xs text-muted">
                共 {numberFormat.format(totalSessions)} 个在线会话
              </p>
            </div>
          </div>

          <div className="card p-5">
            <p className="mb-3 text-sm text-muted">
              登录来源地域分布（近 {days} 天）
            </p>
            {stats.regions_map.length === 0 &&
            stats.regions_other.overseas +
              stats.regions_other.internal +
              stats.regions_other.unknown ===
              0 ? (
              <p className="text-sm text-muted">
                暂无数据：IP 库未安装或统计窗口内无登录。
              </p>
            ) : (
              <ChinaMap
                data={stats.regions_map}
                others={stats.regions_other}
              />
            )}
          </div>
        </div>
      ) : (
        <div className="card p-6 text-sm text-muted">正在加载统计数据…</div>
      )}
    </section>
  );
}
