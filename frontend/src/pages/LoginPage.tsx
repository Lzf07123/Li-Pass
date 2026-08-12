import { useEffect, useState } from "react";
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

type EmailSendStatus = "sent" | "failed" | "rate_limited" | "skipped";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<{ id: string; methods: string[] } | null>(
    null
  );
  const [emailStatus, setEmailStatus] = useState<EmailSendStatus | null>(null);
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);
  const [rememberMe, setRememberMe] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawNext = searchParams.get("next");
  const next = isSafeNext(rawNext) ? rawNext : null;

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setTimeout(() => setResendCountdown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCountdown]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await authApi.login({ email, password, remember_me: rememberMe });
      if (result.requires_2fa && result.challenge_id) {
        const methods = result.methods ?? [];
        setChallenge({ id: result.challenge_id, methods });
        setEmailStatus(result.email_status ?? null);
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
    setVerifying(true);
    try {
      await auth2faApi.verify(challenge.id, method, code);
      if (next) {
        window.location.href = next;
      } else {
        navigate(next || "/");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "验证失败");
    } finally {
      setVerifying(false);
    }
  }

  async function sendCode() {
    if (!challenge) return;
    try {
      await auth2faApi.send(challenge.id);
      toast.success("验证码已重新发送，请查收邮箱");
      setEmailStatus("sent");
      setResendCountdown(60);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发送失败");
      setEmailStatus("failed");
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
          {method === "email_otp" && emailStatus && (
            <p
              className={`text-xs ${
                emailStatus === "sent" ? "text-muted" : "text-warning"
              }`}
            >
              {emailStatus === "sent" &&
                "验证码已发送至你的邮箱，10 分钟内有效；重新发送后旧码自动失效"}
              {emailStatus === "failed" &&
                "验证码发送失败，请点击下方“重新发送邮箱验证码”重试"}
              {emailStatus === "rate_limited" && "验证码发送过于频繁，请稍后再试"}
            </p>
          )}
          <label className="block">
            <span className="label">验证码</span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input"
              placeholder={method === "recovery" ? "恢复码" : "6 位动态码"}
              autoFocus
              inputMode={method === "recovery" ? "text" : "numeric"}
              maxLength={method === "recovery" ? 64 : 6}
              required
            />
          </label>
          <button
            type="submit"
            className="btn btn-primary w-full"
            disabled={verifying}
          >
            {verifying ? "验证中…" : "验证"}
          </button>
          {challenge.methods.includes("email_otp") && (
            <button
              type="button"
              onClick={sendCode}
              className="btn btn-secondary w-full"
              disabled={verifying || resendCountdown > 0}
            >
              {resendCountdown > 0
                ? `重新发送（${resendCountdown}s）`
                : "重新发送邮箱验证码"}
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
        <label className="flex cursor-pointer items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          记住我（30 天内免登录）
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
