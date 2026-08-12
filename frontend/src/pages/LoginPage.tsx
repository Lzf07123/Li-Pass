import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { auth2faApi, authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";
import { useToast } from "../hooks/useToast";
import { APP_NAME } from "../lib/brand";
import { isSafeNext } from "../lib/navigation";

const METHOD_LABELS: Record<string, string> = {
  email_otp: "邮箱验证码",
  totp: "认证器动态码（TOTP）",
  recovery: "恢复码",
};

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<{ id: string; methods: string[] } | null>(
    null
  );
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("");
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawNext = searchParams.get("next");
  const next = isSafeNext(rawNext) ? rawNext : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
      toast.error(err instanceof Error ? err.message : "登录失败");
    }
  }

  async function verifyCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    try {
      await auth2faApi.verify(challenge.id, method, code);
      if (next) {
        window.location.href = next;
      } else {
        navigate(next || "/");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "验证失败");
    }
  }

  async function sendCode() {
    if (!challenge) return;
    try {
      await auth2faApi.send(challenge.id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送失败");
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
