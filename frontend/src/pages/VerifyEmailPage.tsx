import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";
import { useToast } from "../hooks/useToast";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [code, setCode] = useState("");
  const toast = useToast();
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await authApi.verifyEmail({ email, code });
      toast.success(result.message, {
        duration: 8000,
        action: {
          label: "去登录",
          onClick: () => navigate("/login"),
        },
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "验证失败");
    }
  }

  return (
    <AuthShell title="验证邮箱" subtitle={`验证码已发送到 ${email || "你的邮箱"}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-muted">验证码 10 分钟内有效。</p>
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
        <button type="submit" className="btn btn-primary w-full">
          验证
        </button>
      </form>
    </AuthShell>
  );
}
