import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致");
      return;
    }
    try {
      const result = await authApi.confirmPasswordReset({
        email,
        code,
        new_password: newPassword,
      });
      setMessage(result.message);
      setCode("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form
        onSubmit={handleSubmit}
        className="w-96 space-y-4 rounded-xl bg-white p-8 shadow"
      >
        <h1 className="text-2xl font-bold">设置新密码</h1>
        <p className="text-sm text-gray-600">
          输入发送到邮箱的 6 位验证码，并设置新密码。
        </p>
        <label className="block">
          邮箱
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          验证码
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            maxLength={6}
            placeholder="6 位数字"
            required
          />
        </label>
        <label className="block">
          新密码
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            minLength={8}
            placeholder="至少 8 位"
            required
          />
        </label>
        <label className="block">
          确认新密码
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            minLength={8}
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        {message && (
          <p className="text-green-600">
            {message}，<Link to="/login" className="text-blue-600">去登录</Link>
          </p>
        )}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          重置密码
        </button>
        <p>
          <Link to="/login" className="text-blue-600">返回登录</Link>
        </p>
      </form>
    </main>
  );
}
