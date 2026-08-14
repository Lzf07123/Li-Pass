import { useCallback, useEffect, useRef, useState } from "react";

import { adminSettingsApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import type { Ip2regionUpdateStatus, SiteSettings } from "../api/types";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

const UPDATE_INTERVALS = [
  { hours: 12, label: "每 12 小时" },
  { hours: 24, label: "每 24 小时" },
  { hours: 72, label: "每 3 天" },
  { hours: 168, label: "每 7 天" },
] as const;

const UPDATE_STAGE_LABEL: Record<string, string> = {
  checking: "正在检查最新版本",
  downloading_v4: "正在下载 IPv4 库",
  downloading_v6: "正在下载 IPv6 库",
  installing: "正在校验并安装",
};

function formatDataDate(iso: string | null): string {
  if (!iso) return "未知";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "未知"
    : date.toLocaleDateString("zh-CN");
}

export function AdminSettingsPanel() {
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [updateStatus, setUpdateStatus] =
    useState<Ip2regionUpdateStatus | null>(null);
  const toast = useToast();
  const updateToastShownRef = useRef(false);

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

  // 打开面板时先查一次：若后台任务仍在进行（例如离开页面再回来），恢复轮询。
  useEffect(() => {
    let cancelled = false;
    adminSettingsApi
      .ip2regionUpdateStatus()
      .then((status) => {
        if (!cancelled && status.state === "running") {
          setUpdateStatus(status);
        }
      })
      .catch(() => {
        // 初始状态查询失败不打扰用户；点击更新时会再次上报错误。
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const pollUpdateStatus = useCallback(async () => {
    let status: Ip2regionUpdateStatus;
    try {
      status = await adminSettingsApi.ip2regionUpdateStatus();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "获取更新状态失败",
      );
      return;
    }
    setUpdateStatus(status);
    if (status.state === "success" && !updateToastShownRef.current) {
      updateToastShownRef.current = true;
      await load();
      toast.success(
        status.changed
          ? `IP 库已更新到 ${status.version}`
          : `已是最新版本 ${status.version}`,
      );
    } else if (status.state === "error" && !updateToastShownRef.current) {
      updateToastShownRef.current = true;
      toast.error(status.message || "更新失败");
    }
  }, [load, toast]);

  useEffect(() => {
    if (updateStatus?.state !== "running") return;
    const timer = window.setInterval(() => {
      void pollUpdateStatus();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [updateStatus?.state, pollUpdateStatus]);

  const updateAction = useAsyncAction(
    async () => {
      const result = await adminSettingsApi.ip2regionUpdate();
      updateToastShownRef.current = false;
      setUpdateStatus(result.status);
      toast.success("已在后台开始检查更新");
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
          <button
            type="button"
            disabled={
              settings === null ||
              updateStatus?.state === "running" ||
              updateAction.pending
            }
            className="btn btn-secondary"
            onClick={() => void updateAction.run()}
          >
            {updateStatus?.state === "running"
              ? "后台下载中…"
              : "立即检查更新"}
          </button>
        </div>

        {updateStatus && updateStatus.state !== "idle" && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-xs text-muted">
              <span>
                {updateStatus.state === "success"
                  ? "更新完成"
                  : updateStatus.state === "error"
                    ? "更新失败"
                    : UPDATE_STAGE_LABEL[updateStatus.stage] ?? "处理中"}
              </span>
              <span>
                {updateStatus.state === "running"
                  ? `${Number(updateStatus.percent).toFixed(1)}%`
                  : updateStatus.state === "success"
                    ? "100%"
                    : "—"}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{
                  width: `${
                    updateStatus.state === "success"
                      ? 100
                      : Math.max(0, Math.min(100, updateStatus.percent))
                  }%`,
                }}
              />
            </div>
          </div>
        )}

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
