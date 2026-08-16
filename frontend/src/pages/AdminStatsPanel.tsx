import { useCallback, useEffect, useState } from "react";

import { adminStatsApi } from "../api/client";
import type { AdminStats } from "../api/types";
import { AsyncButton } from "../components/AsyncButton";
import { MagicBento } from "../components/bits/MagicBento";
import { LineIcon } from "../components/bits/LineIcon";
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

/** 认证方式分布条：每种方式一个固定色相，与图表/占位瓦片同族 */
const AUTH_METHOD_COLORS: Record<string, string> = {
  password: "var(--portal-accent-cyan)",
  email_otp: "var(--portal-accent-teal)",
  totp: "var(--portal-accent-violet)",
  recovery: "var(--portal-accent-amber)",
};

/** 概览 Bento 卡：六张卡各一个色相（卡面恒为深色，两套主题共用亮色标签） */
const CARD_ACCENTS: Array<{ rgb: string; hex: string }> = [
  { rgb: "var(--portal-bento-sky-rgb)", hex: "var(--portal-bento-sky)" },
  { rgb: "var(--portal-bento-indigo-rgb)", hex: "var(--portal-bento-indigo)" },
  { rgb: "var(--portal-bento-teal-rgb)", hex: "var(--portal-bento-teal)" },
  { rgb: "var(--portal-bento-violet-rgb)", hex: "var(--portal-bento-violet)" },
  { rgb: "var(--portal-bento-amber-rgb)", hex: "var(--portal-bento-amber)" },
  { rgb: "var(--portal-bento-rose-rgb)", hex: "var(--portal-bento-rose)" },
];

const numberFormat = new Intl.NumberFormat("zh-CN");

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

function safeRatio(part: number, total: number): number {
  return total > 0 ? part / total : 0;
}

function percentOf(part: number, total: number): string {
  return `${(safeRatio(part, total) * 100).toFixed(1)}%`;
}

function StatProgress({ ratio }: { ratio: number }) {
  const percent = Math.round(Math.min(1, Math.max(0, ratio)) * 100);
  return (
    <div
      aria-hidden="true"
      className="mt-0.5 h-1 w-full overflow-hidden rounded-full"
      style={{ backgroundColor: "rgba(255, 255, 255, 0.12)" }}
    >
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{
          width: `${percent}%`,
          backgroundColor: "var(--bento-label, #38bdf8)",
        }}
      />
    </div>
  );
}

function StatSparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const width = 160;
  const height = 32;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const points = values.map((value, index) => [
    index * step,
    height - 4 - ((value - min) / range) * (height - 10),
  ]);
  const line = points
    .map(
      ([x, y], index) =>
        `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`,
    )
    .join(" ");
  const area = `${line} L${width},${height} L0,${height} Z`;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="mt-0.5 h-6 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={area} fill="var(--bento-label, #38bdf8)" fillOpacity={0.14} />
      <path
        d={line}
        fill="none"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ stroke: "var(--bento-label, #38bdf8)" }}
      />
    </svg>
  );
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
          color: "var(--portal-accent-teal)",
        },
        {
          name: "新增注册",
          values: stats.daily.map((point) => point.registrations),
          color: "var(--portal-accent-violet)",
          dashed: true,
        },
      ]
    : [];

  const overviewCards = stats
    ? (() => {
        const totalUsers = stats.overview.total_users;
        const registrations = stats.daily.reduce(
          (sum, point) => sum + point.registrations,
          0,
        );
        const dailyLogins =
          stats.daily.length > 0
            ? stats.daily.reduce((sum, point) => sum + point.logins, 0) /
              stats.daily.length
            : 0;
        return [
        {
          title: "账号总数",
          value: numberFormat.format(totalUsers),
          hint: `启用 ${numberFormat.format(stats.overview.active_users)} · 禁用 ${numberFormat.format(stats.overview.disabled_users)}`,
          icon: <LineIcon name="users" className="h-3.5 w-3.5" />,
          href: "/admin/users",
          footer: (
            <StatProgress
              ratio={safeRatio(stats.overview.active_users, totalUsers)}
            />
          ),
        },
        {
          title: "管理员",
          value: numberFormat.format(stats.overview.admins),
          hint: `占账号总数 ${percentOf(stats.overview.admins, totalUsers)}`,
          icon: <LineIcon name="shield" className="h-3.5 w-3.5" />,
          href: "/admin/users",
        },
        {
          title: "已验证邮箱",
          value: numberFormat.format(stats.overview.verified_users),
          hint: `验证率 ${percentOf(stats.overview.verified_users, totalUsers)} · 未验证 ${numberFormat.format(Math.max(0, totalUsers - stats.overview.verified_users))}`,
          icon: <LineIcon name="mail" className="h-3.5 w-3.5" />,
          href: "/admin/users",
          footer: (
            <StatProgress
              ratio={safeRatio(stats.overview.verified_users, totalUsers)}
            />
          ),
        },
        {
          title: "在线会话",
          value: numberFormat.format(stats.overview.online_sessions),
          hint: "当前活跃的登录会话",
          icon: <LineIcon name="monitor" className="h-3.5 w-3.5" />,
          href: "/admin/sessions",
        },
        {
          title: "累计登录次数",
          value: numberFormat.format(stats.overview.total_logins),
          hint: `近 ${days} 天日均 ${numberFormat.format(Math.round(dailyLogins))} 次`,
          icon: <LineIcon name="trend" className="h-3.5 w-3.5" />,
          href: "/admin/audit",
          footer: (
            <StatSparkline
              values={stats.daily.map((point) => point.logins)}
            />
          ),
        },
        {
          title: `新增注册（${days} 天）`,
          value: numberFormat.format(registrations),
          hint: `近 ${days} 天日均 ${(registrations / days).toFixed(1)} 人`,
          icon: <LineIcon name="user" className="h-3.5 w-3.5" />,
          href: "/admin/users",
          footer: (
            <StatSparkline
              values={stats.daily.map((point) => point.registrations)}
            />
          ),
        },
        ].map((card, index) => ({
          ...card,
          accent: CARD_ACCENTS[index],
        }));
      })()
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
              icon: card.icon,
              footer: card.footer,
              href: card.href,
              accent: card.accent,
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
                          className="h-full rounded-full"
                          style={{
                            width: `${(item.count / maxMethodCount) * 100}%`,
                            backgroundColor:
                              AUTH_METHOD_COLORS[item.method] ??
                              "var(--portal-primary)",
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
