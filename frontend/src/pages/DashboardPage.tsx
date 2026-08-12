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

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [apps, setApps] = useState<AppOut[]>([]);
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [nickname, setNickname] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [phone, setPhone] = useState("");
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

  async function bindPhone(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const updated = await meApi.bindPhone({ phone });
      setUser(updated);
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
    try {
      const result = await twofaApi.totpEnable(totpCode, totpSetup.secret);
      setRecoveryCodes(result.recovery_codes);
      setTotpSetup(null);
      setTotpCode("");
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
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">用户中心</h1>
          <div className="flex items-center gap-3">
            {user?.role === "admin" && (
              <Link to="/admin" className="rounded bg-blue-600 p-2 text-white">
                管理后台
              </Link>
            )}
            <button onClick={logout} className="rounded bg-red-600 p-2 text-white">
              退出登录
            </button>
          </div>
        </div>
        {message && <p className="rounded bg-green-50 p-2 text-green-700">{message}</p>}
        {error && <p className="rounded bg-red-50 p-2 text-red-700">{error}</p>}

        {user && (
          <>
            {!user.email_verified && (
              <p className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                邮箱尚未验证：完成验证后才能授权登录接入网站。
                <Link
                  to={`/verify-email?email=${encodeURIComponent(user.email)}`}
                  className="ml-2 font-semibold text-blue-600"
                >
                  去验证
                </Link>
              </p>
            )}
            <section className="rounded-xl bg-white p-6 shadow">
              <h2 className="mb-3 font-semibold">基本资料</h2>
              <p className="mb-3 text-sm text-gray-500">
                邮箱：{user.email}（已验证：{user.email_verified ? "是" : "否"}）｜手机：
                {user.phone ?? "未绑定"}
              </p>
              <div className="mb-3 flex items-center gap-3">
                {user.avatar_url ? (
                  <img
                    src={`${API_BASE_URL}${user.avatar_url}`}
                    alt="头像"
                    className="h-12 w-12 rounded-full object-cover"
                  />
                ) : (
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-lg font-bold text-blue-600">
                    {(user.nickname || user.email).slice(0, 1).toUpperCase()}
                  </span>
                )}
                <p className="text-sm text-gray-500">本地上传头像</p>
              </div>
              <form onSubmit={uploadAvatar} className="mb-3 flex items-end gap-2">
                <label className="block flex-1">
                  选择图片（JPG/PNG/GIF/WebP，≤5MB）
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp"
                    onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
                    className="mt-1 w-full rounded border p-2"
                  />
                </label>
                <button type="submit" className="rounded bg-blue-600 p-2 text-white">
                  上传头像
                </button>
              </form>
              <form onSubmit={saveProfile} className="flex items-end gap-2">
                <label className="block flex-1">
                  昵称
                  <input
                    value={nickname}
                    onChange={(e) => setNickname(e.target.value)}
                    className="mt-1 w-full rounded border p-2"
                  />
                </label>
                <button type="submit" className="rounded bg-blue-600 p-2 text-white">
                  保存
                </button>
              </form>
            </section>
          </>
        )}

        <section className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold">修改密码</h2>
          <form onSubmit={changePassword} className="space-y-3">
            <input
              type="password"
              placeholder="当前密码"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full rounded border p-2"
              required
            />
            <input
              type="password"
              placeholder="新密码（至少 8 位）"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full rounded border p-2"
              minLength={8}
              required
            />
            <button type="submit" className="rounded bg-blue-600 p-2 text-white">
              修改密码
            </button>
          </form>
        </section>

        <section className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold">绑定手机（演示模式）</h2>
          <form onSubmit={bindPhone} className="flex items-end gap-2">
            <label className="block flex-1">
              手机号
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+8613800000000"
                className="mt-1 w-full rounded border p-2"
                required
              />
            </label>
            <button type="submit" className="rounded bg-blue-600 p-2 text-white">
              绑定
            </button>
          </form>
        </section>

        <section className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold">安全设置</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p>邮箱二次验证</p>
                <p className="text-sm text-gray-500">
                  {twofa?.email_otp_enabled ? "已开启" : "未开启"}
                </p>
              </div>
              <button
                onClick={toggleEmailTwofa}
                className="rounded bg-blue-600 p-2 text-white"
              >
                {twofa?.email_otp_enabled ? "关闭" : "开启"}
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p>TOTP 认证器</p>
                <p className="text-sm text-gray-500">
                  {twofa?.totp_enabled
                    ? `已开启（剩余恢复码 ${twofa.recovery_codes_remaining}）`
                    : "未开启"}
                </p>
              </div>
              {twofa?.totp_enabled ? (
                <button onClick={disableTotp} className="rounded bg-red-600 p-2 text-white">
                  关闭
                </button>
              ) : (
                <button
                  onClick={startTotpSetup}
                  className="rounded bg-blue-600 p-2 text-white"
                >
                  开始设置
                </button>
              )}
            </div>

            {totpSetup && (
              <div className="space-y-2 rounded border p-3">
                <p className="text-sm">用认证器扫描二维码或手动输入密钥：</p>
                {totpSetup.qr_data_url && (
                  // eslint-disable-next-line jsx-a11y/alt-text
                  <img src={totpSetup.qr_data_url} className="h-32 w-32" />
                )}
                <p className="break-all text-xs text-gray-500">{totpSetup.otpauth_uri}</p>
                <input
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  placeholder="输入认证器动态码"
                  className="w-full rounded border p-2"
                />
                <button
                  onClick={enableTotp}
                  className="rounded bg-blue-600 p-2 text-white"
                >
                  启用 TOTP
                </button>
              </div>
            )}

            {recoveryCodes && (
              <div className="rounded border border-yellow-300 bg-yellow-50 p-3">
                <p className="mb-2 text-sm font-semibold">
                  请立即保存恢复码（只显示一次）：
                </p>
                <ul className="grid grid-cols-2 gap-1 text-sm">
                  {recoveryCodes.map((code) => (
                    <li key={code}>{code}</li>
                  ))}
                </ul>
              </div>
            )}

            <input
              type="password"
              value={twofaPassword}
              onChange={(e) => setTwofaPassword(e.target.value)}
              placeholder="关闭 2FA 时请输入当前密码"
              className="w-full rounded border p-2"
            />
          </div>
        </section>

        <section className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold">登录设备</h2>
          <ul className="space-y-2">
            {sessions.map((session) => (
              <li key={session.id} className="flex items-center justify-between rounded border p-3">
                <div>
                  <p>
                    {session.device_name || "未命名设备"}
                    {session.current && <span className="ml-2 text-blue-600">（当前）</span>}
                  </p>
                  <p className="text-sm text-gray-500">
                    IP {session.ip}｜最近活动 {new Date(session.last_used_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => revokeSession(session.id)}
                  disabled={session.current}
                  className="rounded bg-gray-200 p-2 disabled:opacity-50"
                >
                  退出
                </button>
              </li>
            ))}
            {sessions.length === 0 && <p className="text-sm text-gray-500">暂无会话</p>}
          </ul>
        </section>

        <section className="rounded-xl bg-white p-6 shadow">
          <h2 className="mb-3 font-semibold">应用广场</h2>
          {apps.length === 0 && <p className="text-sm text-gray-500">还没有已授权的网站</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {apps.map((app) => (
              <div key={app.client_id} className="rounded border p-4">
                <div className="mb-2 flex items-center gap-2">
                  {app.logo_url ? (
                    <img
                      src={app.logo_url}
                      alt={`${app.name} 图标`}
                      className="h-8 w-8 rounded object-contain"
                    />
                  ) : (
                    <span className="flex h-8 w-8 items-center justify-center rounded bg-blue-100 text-sm font-bold text-blue-600">
                      {app.name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                  <p className="font-semibold">{app.name}</p>
                </div>
                <p className="mb-2 text-sm text-gray-500">{app.description}</p>
                {app.home_url && (
                  <a
                    href={app.home_url}
                    className="rounded bg-blue-600 p-2 text-sm text-white"
                  >
                    进入
                  </a>
                )}
                <button
                  onClick={() => revokeApp(app.client_id)}
                  className="ml-2 rounded bg-gray-200 p-2 text-sm"
                >
                  取消授权
                </button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
