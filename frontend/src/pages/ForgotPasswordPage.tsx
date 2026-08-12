import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const toast = useToast();
  const navigate = useNavigate();

  const submitAction = useAsyncAction(
    async (email: string) => {
      const result = await authApi.requestPasswordReset({ email });
      toast.success(result.message, {
        duration: 8000,
        action: {
          label: "去设置新密码",
          onClick: () =>
            navigate(`/reset-password?email=${encodeURIComponent(email)}`),
        },
      });
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "发送失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAction.run(email);
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
        <AsyncButton
          type="submit"
          status={submitAction.status}
          className="btn btn-primary w-full"
        >
          发送重置验证码
        </AsyncButton>
        <p className="text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
