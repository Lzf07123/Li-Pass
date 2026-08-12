import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { auth2faApi, authApi } from "../api/client";

const METHOD_LABELS: Record<string, string> = {
  email_otp: "邮箱验证码",
  totp: "认证器动态码（TOTP）",
  recovery: "恢复码",
};

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [challenge, setChallenge] = useState<{ id: string; methods: string[] } | null>(
    null
  );
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.login({ email, password });
      if (result.requires_2fa && result.challenge_id) {
        const methods = result.methods ?? [];
        setChallenge({ id: result.challenge_id, methods });
        setMethod(
          methods.includes("email_otp")
            ? "email_otp"
            : methods.includes("totp")
              ? "totp"
              : "recovery"
        );
      } else {
        if (next && next.startsWith("http")) {
          window.location.href = next;
        } else {
          navigate(next || "/");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    }
  }

  async function verifyCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    setError("");
    try {
      await auth2faApi.verify(challenge.id, method, code);
      if (next && next.startsWith("http")) {
        window.location.href = next;
      } else {
        navigate(next || "/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    }
  }

  async function sendCode() {
    if (!challenge) return;
    setError("");
    try {
      await auth2faApi.send(challenge.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    }
  }

  if (challenge) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <form onSubmit={verifyCode} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
          <h1 className="text-2xl font-bold">二次验证</h1>
          <p className="text-gray-600">为保护账号安全，请完成二次验证：</p>
          <div className="space-y-2">
            {challenge.methods.map((item) => (
              <label
                key={item}
                className="flex items-center gap-2 rounded border p-2 text-sm"
              >
                <input
                  type="radio"
                  name="twofa-method"
                  value={item}
                  checked={method === item}
                  onChange={(e) => setMethod(e.target.value)}
                />
                {METHOD_LABELS[item] ?? item}
                {item === "recovery" && (
                  <span className="text-xs text-gray-400">
                    （当认证器/邮箱不可用时使用）
                  </span>
                )}
              </label>
            ))}
          </div>
          <label className="block">
            验证码
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="mt-1 w-full rounded border p-2"
              placeholder={method === "recovery" ? "恢复码" : "6 位动态码"}
              required
            />
          </label>
          {error && <p className="text-red-600">{error}</p>}
          <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
            验证
          </button>
          {challenge.methods.includes("email_otp") && (
            <button
              type="button"
              onClick={sendCode}
              className="w-full rounded bg-gray-200 p-2"
            >
              重新发送邮箱验证码
            </button>
          )}
        </form>
      </main>
    );
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
