import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next") ?? "/";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await authApi.login({ email, password });
      navigate(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">登录 Portal OSS</h1>
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
          密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          登录
        </button>
        <p>
          <Link to="/forgot-password" className="text-blue-600">忘记密码？</Link>
          <span className="mx-2">|</span>
          <Link to="/register" className="text-blue-600">注册新账号</Link>
        </p>
      </form>
    </main>
  );
}
