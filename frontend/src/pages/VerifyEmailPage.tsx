import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [code, setCode] = useState("");
  const [resendCountdown, setResendCountdown] = useState(0);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setTimeout(() => setResendCountdown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendCountdown]);

  const submitAction = useAsyncAction(
    async (email: string, code: string) => {
      const result = await authApi.verifyEmail({ email, code });
      toast.success(result.message, {
        duration: 8000,
        action: {
          label: "去登录",
          onClick: () => navigate("/login"),
        },
      });
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "验证失败"),
    },
  );

  const resendAction = useAsyncAction(
    async (email: string) => {
      const result = await authApi.resendVerifyEmail(email);
      setResendCountdown(60);
      toast.success(result.message);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "重新发送失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAction.run(email, code);
  }

  async function resend() {
    if (resendAction.pending || !email) return;
    await resendAction.run(email);
  }

  return (
    <AuthShell title="验证邮箱" subtitle={`验证码已发送到 ${email || "你的邮箱"}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-muted">
          验证码 10 分钟内有效；重新发送后旧验证码立即失效。
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
        <AsyncButton
          type="submit"
          status={submitAction.status}
          className="btn btn-primary w-full"
        >
          验证
        </AsyncButton>
        <button
          type="button"
          onClick={() => void resend()}
          disabled={resendAction.pending || !email || resendCountdown > 0}
          className="btn btn-secondary w-full"
        >
          {resendAction.pending
            ? "发送中…"
            : resendCountdown > 0
              ? `重新发送（${resendCountdown}s）`
              : "重新发送验证码"}
        </button>
      </form>
    </AuthShell>
  );
}
