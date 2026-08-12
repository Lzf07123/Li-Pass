import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { appsApi, authApi, meApi, sessionsApi } from "../api/client";
import type { AppOut, SessionOut, UserOut } from "../api/types";

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [apps, setApps] = useState<AppOut[]>([]);
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [nickname, setNickname] = useState("");
  const [phone, setPhone] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .me()
      .then((data) => {
        setUser(data);
        setNickname(data.nickname);
      })
      .catch(() => navigate("/login"));
    appsApi.list().then(setApps).catch(() => undefined);
    sessionsApi.list().then(setSessions).catch(() => undefined);
  }, [navigate]);

  function showError(err: unknown, fallback: string) {
    setError(err instanceof Error ? err.message : fallback);
  }

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const updated = await meApi.updateProfile({ nickname });
      setUser(updated);
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

  async function revokeSession(id: string) {
    setError("");
    try {
      await sessionsApi.revoke(id);
      setSessions(await sessionsApi.list());
    } catch (err) {
      showError(err, "操作失败");
    }
  }

  async function logout() {
    await authApi.logout();
    navigate("/login");
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">用户中心</h1>
          <button onClick={logout} className="rounded bg-red-600 p-2 text-white">
            退出登录
          </button>
        </div>
        {message && <p className="rounded bg-green-50 p-2 text-green-700">{message}</p>}
        {error && <p className="rounded bg-red-50 p-2 text-red-700">{error}</p>}

        {user && (
          <section className="rounded-xl bg-white p-6 shadow">
            <h2 className="mb-3 font-semibold">基本资料</h2>
            <p className="mb-3 text-sm text-gray-500">
              邮箱：{user.email}（已验证：{user.email_verified ? "是" : "否"}）｜手机：
              {user.phone ?? "未绑定"}
            </p>
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
                <p className="font-semibold">{app.name}</p>
                <p className="mb-2 text-sm text-gray-500">{app.description}</p>
                {app.home_url && (
                  <a
                    href={app.home_url}
                    className="rounded bg-blue-600 p-2 text-sm text-white"
                  >
                    进入
                  </a>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
