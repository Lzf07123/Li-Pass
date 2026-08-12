import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { API_BASE_URL, auth2faApi, authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";
import { APP_NAME } from "../lib/brand";

const METHOD_LABELS: Record<string, string> = {
  email_otp: "邮箱验证码",
  totp: "认证器动态码（TOTP）",
  recovery: "恢复码",
};

export function isSafeNext(value: string | null): boolean {
  if (!value) return false;
  // 相对路径放行（排除 //host 协议相对地址）
  if (value.startsWith("/") && !value.startsWith("//")) return true;
  try {
    const target = new URL(value, window.location.origin);
    const apiOrigin = API_BASE_URL
      ? new URL(API_BASE_URL, window.location.origin).origin
      : window.location.origin;
    return (
      (target.protocol === "http:" || target.protocol === "https:") &&
      (target.origin === window.location.origin || target.origin === apiOrigin)
    );
  } catch {
    return false;
  }
}

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
  const rawNext = searchParams.get("next");
  const next = isSafeNext(rawNext) ? rawNext : null;

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
        if (next) {
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
      if (next) {
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
      <AuthShell title="二次验证" subtitle="为保护账号安全，请完成二次验证">
        <form key="verify" onSubmit={verifyCode} className="animate-fade-up space-y-4">
          <div className="space-y-2">
            {challenge.methods.map((item) => (
              <label
                key={item}
                className={`flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                  method === item
                    ? "border-primary bg-primary-soft text-foreground"
                    : "border-border text-foreground hover:bg-surface-2"
                }`}
              >
                <input
                  type="radio"
                  name="twofa-method"
                  value={item}
                  checked={method === item}
                  onChange={(e) => setMethod(e.target.value)}
                  className="accent-primary"
                />
                {METHOD_LABELS[item] ?? item}
                {item === "recovery" && (
                  <span className="text-xs text-muted">
                    （当认证器/邮箱不可用时使用）
                  </span>
                )}
              </label>
            ))}
          </div>
          <label className="block">
            <span className="label">验证码</span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input"
              placeholder={method === "recovery" ? "恢复码" : "6 位动态码"}
              required
            />
          </label>
          {error && <p className="alert alert-error" role="alert">{error}</p>}
          <button type="submit" className="btn btn-primary w-full">
            验证
          </button>
          {challenge.methods.includes("email_otp") && (
            <button
              type="button"
              onClick={sendCode}
              className="btn btn-secondary w-full"
            >
              重新发送邮箱验证码
            </button>
          )}
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={`登录 ${APP_NAME}`} subtitle="一次注册，通行所有授权网站">
      <form key="login" onSubmit={handleSubmit} className="animate-fade-up space-y-4">
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
        <label className="block">
          <span className="label">密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="alert alert-error" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary w-full">
          登录
        </button>
        <div className="flex items-center justify-center gap-2 text-sm">
          <Link to="/forgot-password" className="btn-link">
            忘记密码？
          </Link>
          <span className="text-border">|</span>
          <Link to="/register" className="btn-link">
            注册新账号
          </Link>
        </div>
      </form>
    </AuthShell>
  );
}
