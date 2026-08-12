import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.verifyEmail({ email, code });
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">验证邮箱</h1>
        <p className="text-gray-600">验证码已发送到 {email || "你的邮箱"}</p>
        <p className="text-xs text-gray-500">
          验证码 10 分钟内有效。开发环境会打印在后端控制台（
          <code>docker compose logs backend | grep "code="</code>）。
        </p>
        <label className="block">
          验证码
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            maxLength={6}
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
          验证
        </button>
      </form>
    </main>
  );
}
