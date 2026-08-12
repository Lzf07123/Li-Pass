import { useEffect, useState } from "react";

import { adminSettingsApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import type { SiteSettings } from "../api/types";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

export function AdminSettingsPanel() {
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const toast = useToast();

  useEffect(() => {
    adminSettingsApi
      .get()
      .then(setSettings)
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载设置失败"),
      );
  }, [toast]);

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
    </section>
  );
}
