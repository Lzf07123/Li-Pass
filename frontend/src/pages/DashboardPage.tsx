import { useEffect, useState } from "react";
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
import { AppHeader } from "../components/AppHeader";

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [apps, setApps] = useState<AppOut[]>([]);
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [nickname, setNickname] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [phone, setPhone] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneStep, setPhoneStep] = useState<"phone" | "code">("phone");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [twofa, setTwofa] = useState<TwoFaStatus | null>(null);
  const [twofaPassword, setTwofaPassword] = useState("");
  const [totpSetup, setTotpSetup] = useState<TotpSetup | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .me()
      .then((data) => {
        setUser(data);
        setNickname(data.nickname);
        setAvatarUrl(data.avatar_url ?? "");
      })
      .catch(() => navigate("/login"));
    appsApi.list().then(setApps).catch(() => undefined);
    sessionsApi.list().then(setSessions).catch(() => undefined);
    twofaApi.status().then(setTwofa).catch(() => undefined);
  }, [navigate]);

  function showError(err: unknown, fallback: string) {
    setError(err instanceof Error ? err.message : fallback);
  }

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const updated = await meApi.updateProfile({
        nickname,
        avatar_url: avatarUrl || null,
      });
      setUser(updated);
      setAvatarUrl(updated.avatar_url ?? "");
      setMessage("资料已保存");
    } catch (err) {
      showError(err, "保存失败");
    }
  }

  async function changePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const result = await meApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setMessage(result.message);
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      showError(err, "修改失败");
    }
  }

  async function sendPhoneCode() {
    setError("");
    setMessage("");
    try {
      await meApi.sendPhoneBind();
      setPhoneStep("code");
      setMessage("验证码已发送至绑定邮箱");
    } catch (err) {
      showError(err, "发送失败");
    }
  }

  async function bindPhone(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const updated = await meApi.bindPhone({ phone, code: phoneCode });
      setUser(updated);
      setPhone("");
      setPhoneCode("");
      setPhoneStep("phone");
      setMessage("手机号已绑定");
    } catch (err) {
      showError(err, "绑定失败");
    }
  }

  async function uploadAvatar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!avatarFile) return;
    setError("");
    setMessage("");
    try {
      const updated = await meApi.uploadAvatar(avatarFile);
      setUser(updated);
      setAvatarUrl(updated.avatar_url ?? "");
      setAvatarFile(null);
      setMessage("头像已更新");
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    }
  }

  async function revokeSession(id: string) {
    setError("");
    try {
      await sessionsApi.revoke(id);
      setSessions(await sessionsApi.list());
    } catch (err) {
      showError(err, "操作失败");
    }
  }

  async function revokeApp(clientId: string) {
    if (!window.confirm("确定取消对该应用的授权吗？")) return;
    setError("");
    try {
      const result = await appsApi.revoke(clientId);
      setApps(apps.filter((app) => app.client_id !== clientId));
      if (result.logout_uri) {
        const next = encodeURIComponent(`${window.location.origin}/`);
        window.location.href = `${result.logout_uri}?next=${next}`;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消授权失败");
    }
  }

  async function logout() {
    await authApi.logout();
    navigate("/login");
  }

  async function toggleEmailTwofa() {
    setError("");
    try {
      if (twofa?.email_otp_enabled) {
        if (!twofaPassword) {
          setError("请输入当前密码以关闭邮箱二次验证");
          return;
        }
        await twofaApi.disableEmail(twofaPassword);
      } else {
        await twofaApi.enableEmail();
      }
      setTwofa(await twofaApi.status());
      setTwofaPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  async function startTotpSetup() {
    setError("");
    try {
      setTotpSetup(await twofaApi.totpSetup());
      setRecoveryCodes(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "启动失败");
    }
  }

  async function enableTotp() {
    if (!totpSetup) return;
    setError("");
    if (!twofaPassword) {
      setError("请输入当前密码以启用 TOTP");
      return;
    }
    try {
      const result = await twofaApi.totpEnable(totpCode, totpSetup.secret, twofaPassword);
      setRecoveryCodes(result.recovery_codes);
      setTotpSetup(null);
      setTotpCode("");
      setTwofaPassword("");
      setTwofa(await twofaApi.status());
    } catch (err) {
      setError(err instanceof Error ? err.message : "启用失败");
    }
  }

  async function disableTotp() {
    setError("");
    if (!twofaPassword) {
      setError("请输入当前密码以关闭 TOTP");
      return;
    }
    try {
      await twofaApi.totpDisable(twofaPassword);
      setTwofa(await twofaApi.status());
      setTwofaPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "关闭失败");
    }
  }

  return (
    <div className="min-h-screen bg-background">
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

      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
        {message && (
          <p className="alert alert-success" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}

        {user && (
          <>
            {!user.email_verified && (
              <p className="alert alert-warning">
                <span>
                  邮箱尚未验证：完成验证后才能授权登录接入网站。
                  <Link
                    to={`/verify-email?email=${encodeURIComponent(user.email)}`}
                    className="btn-link ml-2 font-semibold"
                  >
                    去验证
                  </Link>
                </span>
              </p>
            )}

            <section className="card p-6">
              <h2 className="mb-4 text-base font-semibold text-foreground">
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
                <button type="submit" className="btn btn-primary">
                  上传头像
                </button>
              </form>
              <form onSubmit={saveProfile} className="flex flex-wrap items-end gap-2">
                <label className="block min-w-0 flex-1">
                  <span className="label">昵称</span>
                  <input
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    className="input"
                    required
                  />
                </label>
                <button type="submit" className="btn btn-primary">
                  保存
                </button>
              </form>
            </section>
          </>
        )}

        <section className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-foreground">修改密码</h2>
          <form onSubmit={changePassword} className="space-y-3">
            <input
              type="password"
              placeholder="当前密码"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="input"
              autoComplete="current-password"
              required
            />
            <input
              type="password"
              placeholder="新密码（至少 8 位）"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="input"
              minLength={8}
              autoComplete="new-password"
              required
            />
            <button type="submit" className="btn btn-primary">
              修改密码
            </button>
          </form>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-foreground">
            绑定手机（演示模式）
          </h2>
          {phoneStep === "phone" ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sendPhoneCode();
              }}
              className="flex flex-wrap items-end gap-2"
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
              <button type="submit" className="btn btn-primary">
                发送验证码
              </button>
            </form>
          ) : (
            <form onSubmit={bindPhone} className="flex flex-wrap items-end gap-2">
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
              <button type="submit" className="btn btn-primary">
                确认绑定
              </button>
            </form>
          )}
        </section>

        <section className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-foreground">安全设置</h2>
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium text-foreground">邮箱二次验证</p>
                <p className="mt-0.5 text-sm text-muted">
                  {twofa?.email_otp_enabled ? "已开启" : "未开启"}
                </p>
              </div>
              <button
                onClick={toggleEmailTwofa}
                className={`btn ${twofa?.email_otp_enabled ? "btn-secondary" : "btn-primary"}`}
              >
                {twofa?.email_otp_enabled ? "关闭" : "开启"}
              </button>
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
                <button onClick={disableTotp} className="btn btn-danger">
                  关闭
                </button>
              ) : (
                <button onClick={startTotpSetup} className="btn btn-primary">
                  开始设置
                </button>
              )}
            </div>

            {totpSetup && (
              <div className="space-y-3 rounded-xl border border-border bg-surface-2/50 p-4">
                <p className="text-sm text-foreground">
                  用认证器扫描二维码或手动输入密钥：
                </p>
                {totpSetup.qr_data_url && (
                  // eslint-disable-next-line jsx-a11y/alt-text
                  <img
                    src={totpSetup.qr_data_url}
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
                <button onClick={enableTotp} className="btn btn-primary">
                  启用 TOTP
                </button>
              </div>
            )}

            {recoveryCodes && (
              <div className="alert alert-warning">
                <div className="w-full">
                  <p className="mb-2 text-sm font-semibold">
                    请立即保存恢复码（只显示一次）：
                  </p>
                  <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    {recoveryCodes.map((code) => (
                      <li key={code} className="font-mono">
                        {code}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <input
              type="password"
              value={twofaPassword}
              onChange={(e) => setTwofaPassword(e.target.value)}
              placeholder="关闭 2FA 时请输入当前密码"
              className="input"
              autoComplete="current-password"
            />
          </div>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-foreground">登录设备</h2>
          <ul className="space-y-2">
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
                <button
                  onClick={() => revokeSession(session.id)}
                  disabled={session.current}
                  className="btn btn-secondary"
                >
                  退出
                </button>
              </li>
            ))}
            {sessions.length === 0 && <p className="text-sm text-muted">暂无会话</p>}
          </ul>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 text-base font-semibold text-foreground">应用广场</h2>
          {apps.length === 0 && <p className="text-sm text-muted">还没有已授权的网站</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {apps.map((app) => (
              <div
                key={app.client_id}
                className="flex flex-col gap-3 rounded-xl border border-border p-4"
              >
                <div className="flex items-center gap-2">
                  {app.logo_url ? (
                    <img
                      src={app.logo_url}
                      alt={`${app.name} 图标`}
                      className="h-8 w-8 rounded object-contain"
                    />
                  ) : (
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary-soft text-sm font-bold text-primary">
                      {app.name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                  <p className="truncate font-semibold text-foreground">{app.name}</p>
                </div>
                <p className="line-clamp-2 text-sm text-muted">{app.description}</p>
                <div className="mt-auto flex gap-2">
                  {app.home_url && (
                    <a href={app.home_url} className="btn btn-primary flex-1">
                      进入
                    </a>
                  )}
                  <button
                    onClick={() => revokeApp(app.client_id)}
                    className="btn btn-secondary"
                  >
                    取消授权
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
