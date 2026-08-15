import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { auth2faApi, authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { PasswordInput } from "../components/PasswordInput";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";
import { APP_NAME } from "../lib/brand";
import { isSafeNext } from "../lib/navigation";
import {
  getRememberedAccount,
  getRememberedPassword,
  persistRememberedCredentials,
} from "../lib/remember";

const METHOD_LABELS: Record<string, string> = {
  email_otp: "邮箱验证码",
  totp: "认证器动态码（TOTP）",
  recovery: "恢复码",
};

type EmailSendStatus = "sent" | "failed" | "rate_limited" | "skipped";

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const rawNext = searchParams.get("next");
  const next = isSafeNext(rawNext) ? rawNext : null;
  const emailParam = searchParams.get("email");
  const rememberedAccount = getRememberedAccount();
  const [email, setEmail] = useState(emailParam ?? rememberedAccount ?? "");
  const [password, setPassword] = useState(
    emailParam && emailParam !== rememberedAccount
      ? ""
      : (getRememberedPassword() ?? ""),
  );
  const [challenge, setChallenge] = useState<{ id: string; methods: string[] } | null>(
    null
  );
  const [emailStatus, setEmailStatus] = useState<EmailSendStatus | null>(null);
  const [code, setCode] = useState("");
  const [method, setMethod] = useState("");
  const [resendCountdown, setResendCountdown] = useState(0);
  const [emailRetryAfterSeconds, setEmailRetryAfterSeconds] = useState(3600);
  const [rememberMe, setRememberMe] = useState(false);
  const [rememberAccount, setRememberAccount] = useState(
    rememberedAccount !== null,
  );
  const [rememberPassword, setRememberPassword] = useState(
    getRememberedPassword() !== null,
  );
  const pendingRemember = useRef<{
    email: string;
    password: string;
    account: boolean;
    pwd: boolean;
  } | null>(null);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setTimeout(() => setResendCountdown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCountdown]);

  const loginAction = useAsyncAction(
    async (
      email: string,
      password: string,
      rememberMe: boolean,
      rememberAccount: boolean,
      rememberPassword: boolean,
    ) => {
      const result = await authApi.login({
        email,
        password,
        remember_me: rememberMe,
      });
      if (result.requires_2fa && result.challenge_id) {
        pendingRemember.current = {
          email,
          password,
          account: rememberAccount,
          pwd: rememberPassword,
        };
        const methods = result.methods ?? [];
        setChallenge({ id: result.challenge_id, methods });
        setEmailStatus(result.email_status ?? null);
        setResendCountdown(0);
        setEmailRetryAfterSeconds(result.email_retry_after_seconds ?? 3600);
        setMethod(
          methods.includes("email_otp")
            ? "email_otp"
            : methods.includes("totp")
              ? "totp"
              : "recovery",
        );
      } else if (next) {
        persistRememberedCredentials(
          email,
          password,
          rememberAccount,
          rememberPassword,
        );
        window.location.href = next;
      } else {
        persistRememberedCredentials(
          email,
          password,
          rememberAccount,
          rememberPassword,
        );
        navigate("/");
      }
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "登录失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loginAction.run(
      email,
      password,
      rememberMe,
      rememberAccount,
      rememberPassword,
    );
  }

  const verifyAction = useAsyncAction(
    async (challengeId: string, method: string, code: string) => {
      await auth2faApi.verify(challengeId, method, code);
      if (pendingRemember.current) {
        const pending = pendingRemember.current;
        persistRememberedCredentials(
          pending.email,
          pending.password,
          pending.account,
          pending.pwd,
        );
        pendingRemember.current = null;
      }
      if (next) window.location.href = next;
      else navigate("/");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "验证失败"),
    },
  );

  async function verifyCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) return;
    await verifyAction.run(challenge.id, method, code);
  }

  const sendCodeAction = useAsyncAction(
    async (challengeId: string) => {
      await auth2faApi.send(challengeId);
      toast.success("验证码已发送，请查收邮箱");
      setEmailStatus("sent");
      setResendCountdown(60);
    },
    {
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "发送失败");
        setEmailStatus("failed");
      },
    },
  );

  function sendCode() {
    if (!challenge || sendCodeAction.pending) return;
    void sendCodeAction.run(challenge.id);
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
          {method === "email_otp" && (
            <p
              className={`text-xs ${
                emailStatus === "sent" ? "text-muted" : "text-warning"
              }`}
            >
              {emailStatus === "sent" &&
                "验证码已发送至你的邮箱，10 分钟内有效；重新发送后旧码自动失效"}
              {(!emailStatus || emailStatus === "skipped") &&
                "需要先点击下方按钮获取邮箱验证码"}
              {emailStatus === "failed" &&
                "验证码发送失败，请点击下方按钮重新发送"}
              {emailStatus === "rate_limited" &&
                `验证码发送过于频繁，请在约 ${Math.ceil(
                  emailRetryAfterSeconds / 60,
                )} 分钟后重试`}
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
          <AsyncButton
            type="submit"
            status={verifyAction.status}
            className="btn btn-primary w-full"
          >
            验证
          </AsyncButton>
          {challenge.methods.includes("email_otp") && (
            <AsyncButton
              type="button"
              status={sendCodeAction.status}
              onClick={() => void sendCode()}
              className="btn btn-secondary w-full"
              disabled={verifyAction.pending || resendCountdown > 0}
            >
              {resendCountdown > 0
                ? `重新发送（${resendCountdown}s）`
                : emailStatus === "sent"
                  ? "重新发送邮箱验证码"
                  : "获取邮箱验证码"}
            </AsyncButton>
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
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            autoComplete="current-password"
            required
          />
        </label>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-foreground">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            记住我（30 天内免登录）
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={rememberAccount}
              onChange={(e) => {
                const checked = e.target.checked;
                setRememberAccount(checked);
                if (!checked) setRememberPassword(false);
              }}
              className="h-4 w-4 accent-primary"
            />
            记住账号
          </label>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={rememberPassword}
              onChange={(e) => {
                const checked = e.target.checked;
                setRememberPassword(checked);
                if (checked) setRememberAccount(true);
              }}
              className="h-4 w-4 accent-primary"
            />
            记住密码
          </label>
        </div>
        <AsyncButton
          type="submit"
          status={loginAction.status}
          className="btn btn-primary w-full"
        >
          登录
        </AsyncButton>
        <div className="flex items-center justify-center gap-2 text-sm">
          <Link to="/forgot-password" className="btn-link">
            忘记密码？
          </Link>
          <span className="text-border">|</span>
          <Link
            to={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
            className="btn-link"
          >
            注册新账号
          </Link>
        </div>
      </form>
    </AuthShell>
  );
}
