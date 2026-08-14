import { useCallback, useEffect, useState } from "react";

import { adminSettingsApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import type { SiteSettings } from "../api/types";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const UPDATE_INTERVALS = [
  { hours: 12, label: "每 12 小时" },
  { hours: 24, label: "每 24 小时" },
  { hours: 72, label: "每 3 天" },
  { hours: 168, label: "每 7 天" },
] as const;

function formatDataDate(iso: string | null): string {
  if (!iso) return "未知";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "未知"
    : date.toLocaleDateString("zh-CN");
}

export function AdminSettingsPanel() {
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const toast = useToast();

  const load = useCallback(
    () =>
      adminSettingsApi
        .get()
        .then(setSettings)
        .catch((err) =>
          toast.error(err instanceof Error ? err.message : "加载设置失败"),
        ),
    [toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const toggleAction = useAsyncAction(
    async (settings: SiteSettings) => {
      const next = {
        public_registration_enabled: !settings.public_registration_enabled,
      };
      const updated = await adminSettingsApi.update(next);
      setSettings(updated);
      toast.success(
        updated.public_registration_enabled
          ? "已开启公开注册"
          : "已关闭公开注册，仅接受邀请注册",
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "保存设置失败"),
    },
  );

  function toggleRegistration() {
    if (!settings) return;
    void toggleAction.run(settings);
  }

  const toggleAutoAction = useAsyncAction(
    async () => {
      if (!settings) return;
      const next = !settings.ip2region.auto_update_enabled;
      const updated = await adminSettingsApi.update({
        public_registration_enabled: settings.public_registration_enabled,
        ip2region_auto_update_enabled: next,
      });
      setSettings(updated);
      toast.success(
        next ? "已开启 IP 库自动更新" : "已关闭 IP 库自动更新",
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "保存设置失败"),
    },
  );

  const intervalAction = useAsyncAction(
    async (hours: number) => {
      if (!settings) return;
      const updated = await adminSettingsApi.update({
        public_registration_enabled: settings.public_registration_enabled,
        ip2region_update_interval_hours: hours,
      });
      setSettings(updated);
      toast.success(`IP 库检查间隔已设为每 ${hours} 小时`);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "保存设置失败"),
    },
  );

  const updateAction = useAsyncAction(
    async () => {
      const result = await adminSettingsApi.ip2regionUpdate();
      await load();
      toast.success(
        result.changed
          ? `IP 库已更新到 ${result.version}`
          : `已是最新版本 ${result.version}`,
      );
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "更新失败"),
    },
  );

  const currentInterval = settings?.ip2region.update_interval_hours ?? 24;
  const intervalOptions = UPDATE_INTERVALS.some(
    (option) => option.hours === currentInterval,
  )
    ? UPDATE_INTERVALS
    : [
        ...UPDATE_INTERVALS,
        { hours: currentInterval, label: `每 ${currentInterval} 小时` },
      ];

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">站点设置</h2>
      <div className="card p-6">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="font-medium text-foreground">公开注册</p>
            <p className="mt-0.5 text-sm text-muted">
              {settings === null
                ? "加载中…"
                : settings.public_registration_enabled
                  ? "已开启"
                  : "已关闭"}
            </p>
            <p className="mt-2 text-xs text-muted">
              关闭后新用户无法通过注册页自助注册，仅可凭管理员发送的邀请链接注册；
              注册页会提示“注册渠道暂时关闭，只接收邀请注册”。
            </p>
          </div>
          <AsyncButton
            type="button"
            status={toggleAction.status}
            disabled={settings === null}
            className={`btn ${
              settings?.public_registration_enabled
                ? "btn-secondary"
                : "btn-primary"
            }`}
            onClick={() => void toggleRegistration()}
          >
            {settings?.public_registration_enabled ? "关闭" : "开启"}
          </AsyncButton>
        </div>
      </div>

      <div className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-medium text-foreground">
              IP 归属地库（ip2region）
            </p>
            <p className="mt-0.5 text-sm text-muted">
              {settings === null
                ? "加载中…"
                : `版本 ${settings.ip2region.version ?? "未安装"} · 数据 ${formatDataDate(settings.ip2region.data_updated_at)}`}
            </p>
            <p className="mt-1 text-xs text-muted">
              {settings === null
                ? "用于会话/审计归属地展示与登录地域统计"
                : `IPv4 ${settings.ip2region.v4_ready ? "已加载" : "未加载"} · IPv6 ${settings.ip2region.v6_ready ? "已加载" : "未加载"} · 用于会话/审计归属地展示与登录地域统计`}
            </p>
          </div>
          <AsyncButton
            type="button"
            status={updateAction.status}
            disabled={settings === null}
            className="btn btn-secondary"
            onClick={() => void updateAction.run()}
          >
            立即检查更新
          </AsyncButton>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-border pt-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted">自动更新</span>
            <AsyncButton
              type="button"
              status={toggleAutoAction.status}
              disabled={settings === null}
              className={`btn ${
                settings?.ip2region.auto_update_enabled
                  ? "btn-secondary"
                  : "btn-primary"
              }`}
              onClick={() => void toggleAutoAction.run()}
            >
              {settings?.ip2region.auto_update_enabled
                ? "关闭自动更新"
                : "开启自动更新"}
            </AsyncButton>
          </div>
          <label className="flex items-center gap-2 text-sm text-foreground">
            <span>检查间隔</span>
            <select
              value={currentInterval}
              disabled={settings === null || intervalAction.pending}
              onChange={(event) => void intervalAction.run(Number(event.target.value))}
              className="input-sm"
              aria-label="IP 库检查间隔"
            >
              {intervalOptions.map((option) => (
                <option key={option.hours} value={option.hours}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </section>
  );
}
