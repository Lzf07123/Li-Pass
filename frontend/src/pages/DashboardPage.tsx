import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  API_BASE_URL,
  appsApi,
  authApi,
  meApi,
  sessionsApi,
  twofaApi,
} from "../api/client";
import type { AppOut, SessionOut, TotpSetup, TwoFaStatus, UserOut } from "../api/types";
import { AnimatedNumber } from "../components/AnimatedNumber";
import { AppHeader } from "../components/AppHeader";
import { AsyncButton } from "../components/AsyncButton";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FloatingBackground } from "../components/FloatingBackground";
import { Modal } from "../components/Modal";
import { PasswordInput } from "../components/PasswordInput";
import { SiteFooter } from "../components/SiteFooter";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useBreathOnChange } from "../hooks/useBreathOnChange";
import { useToast } from "../hooks/useToast";
import { FadeIn } from "../components/bits/FadeIn";
import { LineIcon } from "../components/bits/LineIcon";

// 绑定手机功能暂未完善：置为 true 即恢复显示（代码与接口保留）。
const PHONE_BINDING_ENABLED = false;

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [apps, setApps] = useState<AppOut[]>([]);
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [nickname, setNickname] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [phone, setPhone] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneStep, setPhoneStep] = useState<"phone" | "code">("phone");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changePasswordError, setChangePasswordError] = useState<string | null>(null);
  const [twofaPasswordError, setTwofaPasswordError] = useState<string | null>(null);
  const [deleteAccountError, setDeleteAccountError] = useState<string | null>(null);
  const [twofa, setTwofa] = useState<TwoFaStatus | null>(null);
  const [twofaPassword, setTwofaPassword] = useState("");
  const [totpSetup, setTotpSetup] = useState<TotpSetup | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<AppOut | null>(null);
  const [revokeAllOpen, setRevokeAllOpen] = useState(false);
  const [revokeSessionId, setRevokeSessionId] = useState<string | null>(null);
  const [twofaBusy, setTwofaBusy] = useState<
    "email" | "totp-setup" | "totp-enable" | "totp-disable" | null
  >(null);
  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false);
  const [deleteAccountPassword, setDeleteAccountPassword] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const navigate = useNavigate();
  const toast = useToast();
  const sessionsBreathing = useBreathOnChange(sessions);
  const appsBreathing = useBreathOnChange(apps);
  const emailNoticeId = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    // 先确认登录态再并行拉取其余数据：未登录访问首页时只发 1 个请求
    // 而不是 4 个，避免无效鉴权请求占用连接与数据库线程池。
    authApi
      .me()
      .then((data) => {
        if (cancelled) return;
        setUser(data);
        setNickname(data.nickname);
        setAvatarUrl(data.avatar_url ?? "");
        setEmailNotifications(data.email_notifications);
        appsApi
          .list()
          .then((data) => {
            if (!cancelled) setApps(data);
          })
          .catch(() => undefined);
        sessionsApi
          .list()
          .then((data) => {
            if (!cancelled) setSessions(data);
          })
          .catch(() => undefined);
        twofaApi
          .status()
          .then((data) => {
            if (!cancelled) setTwofa(data);
          })
          .catch(() => undefined);
      })
      .catch(() => navigate("/login"));
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function showError(err: unknown, fallback: string) {
    toast.error(err instanceof Error ? err.message : fallback);
  }

  const saveProfileAction = useAsyncAction(
    async (
      nickname: string,
      avatarUrl: string,
      emailNotifications: boolean
    ) => {
      const updated = await meApi.updateProfile({
        nickname,
        avatar_url: avatarUrl || null,
        email_notifications: emailNotifications,
      });
      setUser(updated);
      setAvatarUrl(updated.avatar_url ?? "");
      setEmailNotifications(updated.email_notifications);
      toast.success("资料已保存");
    },
    {
      onError: (err) => showError(err, "保存失败"),
    },
  );

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await saveProfileAction.run(nickname, avatarUrl, emailNotifications);
  }

  const changePasswordAction = useAsyncAction(
    async (currentPassword: string, newPassword: string) => {
      const result = await meApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success(result.message);
      setCurrentPassword("");
      setNewPassword("");
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "修改失败";
        if (message.includes("当前密码")) setChangePasswordError(message);
        else toast.error(message);
      },
    },
  );

  async function changePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await changePasswordAction.run(currentPassword, newPassword);
  }

  const sendPhoneCodeAction = useAsyncAction(
    async () => {
      await meApi.sendPhoneBind();
      setPhoneStep("code");
      toast.success("验证码已发送至绑定邮箱");
    },
    {
      onError: (err) => showError(err, "发送失败"),
    },
  );

  async function sendPhoneCode() {
    await sendPhoneCodeAction.run();
  }

  const bindPhoneAction = useAsyncAction(
    async (phone: string, code: string) => {
      const updated = await meApi.bindPhone({ phone, code });
      setUser(updated);
      setPhone("");
      setPhoneCode("");
      setPhoneStep("phone");
      toast.success("手机号已绑定");
    },
    {
      onError: (err) => showError(err, "绑定失败"),
    },
  );

  async function bindPhone(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await bindPhoneAction.run(phone, phoneCode);
  }

  const uploadAvatarAction = useAsyncAction(
    async (file: File) => {
      const updated = await meApi.uploadAvatar(file);
      setUser(updated);
      setAvatarUrl(updated.avatar_url ?? "");
      setAvatarFile(null);
      toast.success("头像已更新");
    },
    {
      onError: (err) => showError(err, "上传失败"),
    },
  );

  async function uploadAvatar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!avatarFile) return;
    await uploadAvatarAction.run(avatarFile);
  }

  const revokeSessionAction = useAsyncAction(
    async (id: string) => {
      await sessionsApi.revoke(id);
      setSessions(await sessionsApi.list());
      setRevokeSessionId(null);
      toast.success("已退出该设备");
    },
    {
      onError: (err) => showError(err, "操作失败"),
    },
  );

  function revokeSession(id: string) {
    setRevokeSessionId(id);
    void revokeSessionAction.run(id);
  }

  const revokeAllAction = useAsyncAction(
    async () => {
      const result = await sessionsApi.revokeAll();
      setSessions(await sessionsApi.list());
      setRevokeAllOpen(false);
      toast.success(
        result.revoked > 0
          ? `已退出 ${result.revoked} 台设备`
          : "当前没有其他设备需要退出",
      );
    },
    {
      onError: (err) => showError(err, "退出所有设备失败"),
    },
  );

  const revokeAppAction = useAsyncAction(
    async (clientId: string, name: string) => {
      const result = await appsApi.revoke(clientId);
      setApps((prev) => prev.filter((app) => app.client_id !== clientId));
      setRevokeTarget(null);
      toast.success(`已取消对“${name}”的授权`);
      if (result.logout_uri) {
        const next = encodeURIComponent(`${window.location.origin}/`);
        window.location.href = `${result.logout_uri}?next=${next}`;
      }
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "取消授权失败"),
    },
  );

  function confirmRevoke() {
    if (!revokeTarget) return;
    void revokeAppAction.run(revokeTarget.client_id, revokeTarget.name);
  }

  async function logout() {
    const result = await authApi.logout();
    window.location.assign(result.redirect_to ?? "/login");
  }

  async function toggleEmailTwofa() {
    if (twofaBusy !== null || twofa === null) return;
    if (!twofaPassword) {
      setTwofaPasswordError("请输入当前密码");
      return;
    }
    const enabling = !twofa.email_otp_enabled;
    setTwofaBusy("email");
    try {
      const result = enabling
        ? await twofaApi.enableEmail(twofaPassword)
        : await twofaApi.disableEmail(twofaPassword);
      setTwofa(await twofaApi.status());
      setTwofaPassword("");
      setTwofaPasswordError(null);
      toast.success(result.message);
    } catch (err) {
      const message = err instanceof Error ? err.message : "操作失败";
      if (message.includes("当前密码")) {
        setTwofaPasswordError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setTwofaBusy(null);
    }
  }

  async function startTotpSetup() {
    if (twofaBusy !== null) return;
    setTwofaBusy("totp-setup");
    try {
      setTotpSetup(await twofaApi.totpSetup());
      setRecoveryCodes(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "启动失败");
    } finally {
      setTwofaBusy(null);
    }
  }

  async function enableTotp() {
    if (!totpSetup || twofaBusy !== null) return;
    if (!twofaPassword) {
      setTwofaPasswordError("请输入当前密码");
      return;
    }
    if (!totpCode.trim()) {
      toast.error("请输入认证器动态码");
      return;
    }
    setTwofaBusy("totp-enable");
    try {
      const result = await twofaApi.totpEnable(totpCode, totpSetup.secret, twofaPassword);
      setRecoveryCodes(result.recovery_codes);
      setTotpSetup(null);
      setTotpCode("");
      setTwofaPassword("");
      setTwofaPasswordError(null);
      setTwofa(await twofaApi.status());
      toast.success(result.message);
    } catch (err) {
      const message = err instanceof Error ? err.message : "启用失败";
      if (message.includes("当前密码")) {
        setTwofaPasswordError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setTwofaBusy(null);
    }
  }

  async function disableTotp() {
    if (twofaBusy !== null) return;
    if (!twofaPassword) {
      setTwofaPasswordError("请输入当前密码");
      return;
    }
    setTwofaBusy("totp-disable");
    try {
      const result = await twofaApi.totpDisable(twofaPassword);
      setTwofa(await twofaApi.status());
      setTwofaPassword("");
      setTwofaPasswordError(null);
      toast.success(result.message);
    } catch (err) {
      const message = err instanceof Error ? err.message : "关闭失败";
      if (message.includes("当前密码")) {
        setTwofaPasswordError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setTwofaBusy(null);
    }
  }

  const deleteAccountAction = useAsyncAction(
    async (password: string) => {
      const result = await meApi.deleteAccount(password);
      setDeleteAccountOpen(false);
      setDeleteAccountPassword("");
      toast.success(result.message);
      navigate("/login");
    },
    {
      onError: (err) => {
        const message = err instanceof Error ? err.message : "注销失败";
        if (message.includes("当前密码")) setDeleteAccountError(message);
        else toast.error(message);
      },
    },
  );

  async function submitDeleteAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!deleteAccountPassword) {
      setDeleteAccountError("请输入当前密码以确认注销账号");
      return;
    }
    await deleteAccountAction.run(deleteAccountPassword);
  }

  useEffect(() => {
    if (!user) return;
    if (user.email_verified) {
      if (emailNoticeId.current != null) {
        toast.dismiss(emailNoticeId.current);
        emailNoticeId.current = null;
      }
      return;
    }
    if (emailNoticeId.current == null) {
      emailNoticeId.current = toast.warning(
        "邮箱尚未验证，完成验证后才能授权登录接入网站。",
        {
          duration: 0,
          action: {
            label: "去验证",
            onClick: () =>
              navigate(`/verify-email?email=${encodeURIComponent(user.email)}`),
          },
        },
      );
    }
  }, [user, toast, navigate]);

  return (
    <div className="relative flex min-h-screen flex-col bg-background">
      {/* 环境呼吸层：活跃但不打扰；开启滚动风速，静止慢呼吸、滚动如风吹 */}
      <FloatingBackground theme="auto" transparent scrollWind shapeCount={10} />
      <AppHeader
        title="用户中心"
        actions={
          <>
            {user?.role === "admin" && (
              <Link to="/admin" className="btn btn-secondary">
                管理后台
              </Link>
            )}
            <button onClick={logout} className="btn btn-danger">
              退出登录
            </button>
          </>
        }
      />

      <main className="relative mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        {user && (
          <>
            <FadeIn delay={0}>
              <section className="card p-6">
                <h2 className="mb-4 inline-flex items-center gap-2 text-base font-semibold text-foreground">
                  <LineIcon name="user" className="h-4 w-4 text-primary" />
                  基本资料
                </h2>
                <p className="mb-4 text-sm text-muted">
                  邮箱：{user.email}（已验证：{user.email_verified ? "是" : "否"}）｜
                  手机：{user.phone ?? "未绑定"}
                </p>
                <div className="mb-4 flex items-center gap-3">
                  {user.avatar_url ? (
                    <img
                      src={`${API_BASE_URL}${user.avatar_url}`}
                      alt="头像"
                      className="h-12 w-12 rounded-full border border-border object-cover"
                    />
                  ) : (
                    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-lg font-bold text-primary">
                      {(user.nickname || user.email).slice(0, 1).toUpperCase()}
                    </span>
                  )}
                  <p className="text-sm text-muted">本地上传头像</p>
                </div>
                <form onSubmit={uploadAvatar} className="mb-4 flex flex-wrap items-end gap-2">
                  <label className="block min-w-0 flex-1">
                    <span className="label">选择图片（JPG/PNG/GIF/WebP，≤5MB）</span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/gif,image/webp"
                      onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
                      className="input file:cursor-pointer file:mr-3 file:rounded-md file:border-0 file:bg-surface-2 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground"
                    />
                  </label>
                  <AsyncButton
                    type="submit"
                    status={uploadAvatarAction.status}
                    className="btn btn-primary"
                  >
                    上传头像
                  </AsyncButton>
                </form>
                <form onSubmit={saveProfile} className="space-y-3">
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="block min-w-0 flex-1">
                      <span className="label">昵称</span>
                      <input
                        value={nickname}
                        onChange={(e) => setNickname(e.target.value)}
                        className="input"
                        required
                      />
                    </label>
                    <AsyncButton
                      type="submit"
                      status={saveProfileAction.status}
                      className="btn btn-primary"
                    >
                      保存
                    </AsyncButton>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={emailNotifications}
                      onChange={(event) =>
                        setEmailNotifications(event.target.checked)
                      }
                      aria-label="接收邮件通知"
                    />
                    <span>接收邮件通知（关闭后仍会收到站内信）</span>
                  </label>
                </form>
              </section>
            </FadeIn>
          </>
        )}

        <FadeIn delay={0.08}>
          <section className="card p-6">
            <h2 className="mb-4 inline-flex items-center gap-2 text-base font-semibold text-foreground">
              <LineIcon name="lock" className="h-4 w-4 text-primary" />
              修改密码
            </h2>
            <form onSubmit={changePassword} className="space-y-3">
              <div>
                <PasswordInput
                  id="change-current-password"
                  placeholder="当前密码"
                  value={currentPassword}
                  onChange={(e) => {
                    setCurrentPassword(e.target.value);
                    setChangePasswordError(null);
                  }}
                  className="input"
                  autoComplete="current-password"
                  required
                  aria-invalid={changePasswordError ? true : undefined}
                  aria-describedby={
                    changePasswordError
                      ? "change-password-error"
                      : undefined
                  }
                />
                {changePasswordError && (
                  <p
                    id="change-password-error"
                    role="alert"
                    className="mt-1.5 text-xs text-destructive"
                  >
                    {changePasswordError}
                  </p>
                )}
              </div>
              <PasswordInput
                placeholder="新密码（至少 8 位）"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="input"
                minLength={8}
                autoComplete="new-password"
                required
              />
              <AsyncButton
                type="submit"
                status={changePasswordAction.status}
                className="btn btn-primary"
              >
                修改密码
              </AsyncButton>
            </form>
          </section>
        </FadeIn>

        {PHONE_BINDING_ENABLED && (
          <FadeIn delay={0.16}>
            <section className="card p-6">
              <h2 className="mb-4 inline-flex items-center gap-2 text-base font-semibold text-foreground">
                <LineIcon name="phone" className="h-4 w-4 text-primary" />
                绑定手机
              </h2>
              {phoneStep === "phone" ? (
                <form
                  key="phone"
                  onSubmit={(e) => {
                    e.preventDefault();
                    sendPhoneCode();
                  }}
                  className="animate-fade-up flex flex-wrap items-end gap-2"
                >
                  <label className="block min-w-0 flex-1">
                    <span className="label">手机号</span>
                    <input
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="+8613800000000"
                      className="input"
                      inputMode="tel"
                      required
                    />
                  </label>
                  <AsyncButton
                    type="submit"
                    status={sendPhoneCodeAction.status}
                    className="btn btn-primary"
                  >
                    发送验证码
                  </AsyncButton>
                </form>
              ) : (
                <form
                  key="code"
                  onSubmit={bindPhone}
                  className="animate-fade-up flex flex-wrap items-end gap-2"
                >
                  <label className="block min-w-0 flex-1">
                    <span className="label">邮箱验证码</span>
                    <input
                      value={phoneCode}
                      onChange={(e) => setPhoneCode(e.target.value)}
                      placeholder="6 位验证码"
                      className="input"
                      inputMode="numeric"
                      required
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => setPhoneStep("phone")}
                    className="btn btn-secondary"
                  >
                    上一步
                  </button>
                  <AsyncButton
                    type="submit"
                    status={bindPhoneAction.status}
                    className="btn btn-primary"
                  >
                    确认绑定
                  </AsyncButton>
                </form>
              )}
            </section>
          </FadeIn>
        )}

        <FadeIn delay={0.24}>
          <section className="card p-6">
            <h2 className="mb-4 inline-flex items-center gap-2 text-base font-semibold text-foreground">
              <LineIcon name="shield" className="h-4 w-4 text-primary" />
              安全设置
            </h2>
            <div className="space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">邮箱二次验证</p>
                <p className="mt-0.5 text-sm text-muted">
                  {twofa?.email_otp_enabled ? "已开启" : "未开启"}
                </p>
              </div>
              <AsyncButton
                type="button"
                status={twofaBusy === "email" ? "pending" : "idle"}
                onClick={toggleEmailTwofa}
                className={`btn ${twofa?.email_otp_enabled ? "btn-secondary" : "btn-primary"}`}
                disabled={twofa === null || twofaBusy !== null}
              >
                {twofa?.email_otp_enabled ? "关闭" : "开启"}
              </AsyncButton>
            </div>

            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">TOTP 认证器</p>
                <p className="mt-0.5 text-sm text-muted">
                  {twofa?.totp_enabled
                    ? `已开启（剩余恢复码 ${twofa.recovery_codes_remaining}）`
                    : "未开启"}
                </p>
              </div>
              {twofa?.totp_enabled ? (
                <AsyncButton
                  type="button"
                  status={twofaBusy === "totp-disable" ? "pending" : "idle"}
                  onClick={disableTotp}
                  className="btn btn-danger"
                  disabled={twofa === null || twofaBusy !== null}
                >
                  关闭
                </AsyncButton>
              ) : (
                <AsyncButton
                  type="button"
                  status={twofaBusy === "totp-setup" ? "pending" : "idle"}
                  onClick={startTotpSetup}
                  className="btn btn-primary"
                  disabled={twofa === null || twofaBusy !== null}
                >
                  开始设置
                </AsyncButton>
              )}
            </div>

            {totpSetup && (
              <div className="animate-fade-up space-y-3 rounded-xl border border-border bg-surface-2/50 p-4">
                <p className="text-sm text-foreground">
                  用认证器扫描二维码或手动输入密钥：
                </p>
                {totpSetup.qr_data_url && (
                  <img
                    src={totpSetup.qr_data_url}
                    alt="TOTP 绑定二维码"
                    className="h-32 w-32 rounded-lg border border-border bg-white"
                  />
                )}
                <p className="break-all text-xs text-muted">{totpSetup.otpauth_uri}</p>
                <input
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  placeholder="输入认证器动态码"
                  className="input"
                  inputMode="numeric"
                />
                <AsyncButton
                  type="button"
                  status={twofaBusy === "totp-enable" ? "pending" : "idle"}
                  onClick={enableTotp}
                  className="btn btn-primary"
                  disabled={twofaBusy !== null}
                >
                  启用 TOTP
                </AsyncButton>
              </div>
            )}

            <div>
              <PasswordInput
                id="twofa-current-password"
                value={twofaPassword}
                onChange={(e) => {
                  setTwofaPassword(e.target.value);
                  setTwofaPasswordError(null);
                }}
                placeholder="当前密码（开启或关闭 2FA 时使用）"
                className="input"
                autoComplete="current-password"
                disabled={twofaBusy !== null}
                aria-invalid={twofaPasswordError ? true : undefined}
                aria-describedby={
                  twofaPasswordError ? "twofa-password-error" : undefined
                }
              />
              {twofaPasswordError && (
                <p
                  id="twofa-password-error"
                  role="alert"
                  className="mt-1.5 text-xs text-destructive"
                >
                  {twofaPasswordError}
                </p>
              )}
            </div>
            </div>
          </section>
        </FadeIn>

        <FadeIn delay={0.32}>
          <section className="card p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="inline-flex items-center gap-2 text-base font-semibold text-foreground">
                <LineIcon name="monitor" className="h-4 w-4 text-primary" />
                登录设备
                <span className="ml-2 text-sm font-normal text-muted">
                  共 <AnimatedNumber value={sessions.length} /> 个会话
                </span>
              </h2>
              <button
                type="button"
                onClick={() => setRevokeAllOpen(true)}
                disabled={sessions.length <= 1 || revokeAllAction.pending}
                className="btn btn-danger"
              >
                退出所有设备
              </button>
            </div>
            <ul className={`space-y-2 ${sessionsBreathing ? "animate-breath" : ""}`}>
              {sessions.map((session) => (
                <li
                  key={session.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border px-4 py-3"
                >
                  <div>
                    <p className="font-medium text-foreground">
                      {session.device_name || "未命名设备"}
                      {session.current && (
                        <span className="badge badge-primary ml-2">当前</span>
                      )}
                    </p>
                    <p className="mt-0.5 text-sm text-muted">
                      IP {session.ip}｜最近活动{" "}
                      {new Date(session.last_used_at).toLocaleString()}
                    </p>
                  </div>
                  <AsyncButton
                    type="button"
                    status={
                      revokeSessionAction.pending &&
                      revokeSessionId === session.id
                        ? "pending"
                        : "idle"
                    }
                    onClick={() => revokeSession(session.id)}
                    disabled={session.current}
                    className="btn btn-secondary"
                  >
                    退出
                  </AsyncButton>
                </li>
              ))}
              {sessions.length === 0 && (
                <p className="text-sm text-muted">
                  暂无会话，登录新设备后会出现在这里。
                </p>
              )}
            </ul>
          </section>
        </FadeIn>

        <FadeIn delay={0.4}>
          <section className="card p-6">
            <h2 className="mb-4 inline-flex items-center gap-2 text-base font-semibold text-foreground">
              <LineIcon name="grid" className="h-4 w-4 text-primary" />
              应用广场
              <span className="ml-2 text-sm font-normal text-muted">
                共 <AnimatedNumber value={apps.length} /> 个网站
              </span>
            </h2>
            {apps.length === 0 && (
              <p className="text-sm text-muted">
                还没有已授权的网站，在接入网站完成一次授权登录后会自动出现在这里。
              </p>
            )}
            <div className={`flex flex-col gap-3 ${appsBreathing ? "animate-breath" : ""}`}>
              {apps.map((app) => (
                <div
                  key={app.client_id}
                  className="card-interactive flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-border bg-surface px-4 py-3"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    {app.logo_url ? (
                      <img
                        src={app.logo_url}
                        alt={`${app.name} 图标`}
                        className="h-8 w-8 shrink-0 rounded object-contain"
                      />
                    ) : (
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary-soft text-sm font-bold text-primary">
                        {app.name.slice(0, 1).toUpperCase()}
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold text-foreground">
                        {app.name}
                      </p>
                      {app.description && (
                        <p className="truncate text-sm text-muted">
                          {app.description}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="ml-auto flex shrink-0 items-center gap-2">
                    {app.home_url && (
                      <a
                        href={app.home_url}
                        className="btn btn-primary"
                      >
                        进入
                      </a>
                    )}
                    <button
                      onClick={() => setRevokeTarget(app)}
                      className="btn btn-secondary"
                    >
                      取消授权
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </FadeIn>

        <FadeIn delay={0.48}>
          <section className="card border-destructive/25 p-6">
            <h2 className="mb-2 inline-flex items-center gap-2 text-base font-semibold text-destructive">
              <LineIcon name="alert" className="h-4 w-4" />
              注销账号
            </h2>
            <p className="mb-4 text-sm text-muted">
              注销后账号与全部关联数据（会话、授权记录、恢复码、头像等）将被永久删除，
              无法恢复。
            </p>
            <button
              onClick={() => {
                setDeleteAccountPassword("");
                setDeleteAccountOpen(true);
              }}
              className="btn btn-danger"
            >
              注销账号
            </button>
          </section>
        </FadeIn>
      </main>

      <ConfirmDialog
        open={revokeTarget !== null}
        title="取消应用授权"
        message={
          revokeTarget && (
            <span>确定取消对“{revokeTarget.name}”的授权吗？</span>
          )
        }
        status={revokeAppAction.status}
        confirmLabel="确认取消"
        onConfirm={confirmRevoke}
        onCancel={() => {
          if (!revokeAppAction.pending) setRevokeTarget(null);
        }}
      />

      <ConfirmDialog
        open={revokeAllOpen}
        title="退出所有设备"
        message={
          <span>
            确定退出除当前设备外的 {Math.max(0, sessions.length - 1)}{" "}
            台设备吗？其他设备上的登录会话将全部失效。
          </span>
        }
        status={revokeAllAction.status}
        confirmLabel="全部退出"
        onConfirm={() => void revokeAllAction.run()}
        onCancel={() => {
          if (!revokeAllAction.pending) setRevokeAllOpen(false);
        }}
      />

      <Modal
        open={recoveryCodes !== null}
        onClose={() => setRecoveryCodes(null)}
        title="恢复码（只显示一次）"
        intent="warning"
        maxWidth="max-w-lg"
        footer={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setRecoveryCodes(null)}
          >
            我已保存
          </button>
        }
      >
        <p className="mb-3">请立即将以下恢复码保存到安全位置，遗失后无法找回。</p>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-lg bg-surface-2 p-3 text-sm text-foreground">
          {recoveryCodes?.map((code) => (
            <li key={code} className="font-mono">
              {code}
            </li>
          ))}
        </ul>
      </Modal>

      <Modal
        open={deleteAccountOpen}
        onClose={() => {
          if (!deleteAccountAction.pending) setDeleteAccountOpen(false);
        }}
        title="注销账号"
        intent="danger"
        footer={
          <>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setDeleteAccountOpen(false)}
              disabled={deleteAccountAction.pending}
            >
              取消
            </button>
            <AsyncButton
              type="submit"
              form="delete-account-form"
              status={deleteAccountAction.status}
              className="btn btn-danger"
            >
              永久注销
            </AsyncButton>
          </>
        }
      >
        <form
          id="delete-account-form"
          onSubmit={submitDeleteAccount}
          className="space-y-3"
        >
          <p className="text-foreground">
            此操作将永久删除账号及全部关联数据，且不可恢复。请确认这是你本人操作。
          </p>
          <label className="block">
            <span className="label">当前密码</span>
            <PasswordInput
              value={deleteAccountPassword}
              onChange={(e) => {
                setDeleteAccountPassword(e.target.value);
                setDeleteAccountError(null);
              }}
              placeholder="输入当前密码确认注销"
              className="input"
              autoComplete="current-password"
              autoFocus
              aria-invalid={deleteAccountError ? true : undefined}
              aria-describedby={
                deleteAccountError ? "delete-account-error" : undefined
              }
            />
            {deleteAccountError && (
              <p
                id="delete-account-error"
                role="alert"
                className="mt-1.5 text-xs text-destructive"
              >
                {deleteAccountError}
              </p>
            )}
          </label>
        </form>
      </Modal>
      <SiteFooter />
    </div>
  );
}
