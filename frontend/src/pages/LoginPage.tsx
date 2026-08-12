import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { auth2faApi, authApi } from "../api/client";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [challenge, setChallenge] = useState<{ id: string; methods: string[] } | null>(
    null
  );
  const [code, setCode] = useState("");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.login({ email, password });
      if (result.requires_2fa && result.challenge_id) {
        setChallenge({ id: result.challenge_id, methods: result.methods ?? [] });
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
      const method = challenge.methods.includes("email_otp")
        ? "email_otp"
        : challenge.methods.includes("totp")
          ? "totp"
          : "recovery";
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
          <p className="text-gray-600">
            可用方式：{challenge.methods.join("、")}
          </p>
          <label className="block">
            验证码
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="mt-1 w-full rounded border p-2"
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
