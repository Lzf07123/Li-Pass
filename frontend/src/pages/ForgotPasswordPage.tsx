import { useState } from "react";
import { Link } from "react-router-dom";

import { authApi } from "../api/client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.requestPasswordReset({ email });
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">找回密码</h1>
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
        {error && <p className="text-red-600">{error}</p>}
        {message && (
          <div className="space-y-2 rounded bg-green-50 p-3 text-sm text-green-700">
            <p>{message}</p>
            <p>
              收到验证码后，{" "}
              <Link
                to={`/reset-password?email=${encodeURIComponent(email)}`}
                className="font-semibold text-blue-600"
              >
                去设置新密码
              </Link>
            </p>
          </div>
        )}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          发送重置验证码
        </button>
        <p>
          <Link to="/login" className="text-blue-600">返回登录</Link>
        </p>
      </form>
    </main>
  );
}
