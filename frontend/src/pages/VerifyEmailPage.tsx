import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";

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
    <AuthShell title="验证邮箱" subtitle={`验证码已发送到 ${email || "你的邮箱"}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-muted">
          验证码 10 分钟内有效。开发环境会打印在后端控制台（
          <code className="rounded bg-surface-2 px-1 py-0.5">
            docker compose logs backend | grep "code="
          </code>
          ）。
        </p>
        <label className="block">
          <span className="label">验证码</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="input"
            maxLength={6}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
          />
        </label>
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="alert alert-success">
            <span>
              {message}，{" "}
              <Link to="/login" className="btn-link font-semibold">
                去登录
              </Link>
            </span>
          </p>
        )}
        <button type="submit" className="btn btn-primary w-full">
          验证
        </button>
      </form>
    </AuthShell>
  );
}
