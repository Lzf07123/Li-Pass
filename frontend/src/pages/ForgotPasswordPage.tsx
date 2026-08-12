import { useState } from "react";
import { Link } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";

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
    <AuthShell title="找回密码" subtitle="输入注册邮箱，我们将发送重置验证码">
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="label">邮箱</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            autoComplete="email"
            required
          />
        </label>
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}
        {message && (
          <div className="alert alert-success">
            <p>{message}</p>
            <p>
              收到验证码后，{" "}
              <Link
                to={`/reset-password?email=${encodeURIComponent(email)}`}
                className="btn-link font-semibold"
              >
                去设置新密码
              </Link>
            </p>
          </div>
        )}
        <button type="submit" className="btn btn-primary w-full">
          发送重置验证码
        </button>
        <p className="text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
