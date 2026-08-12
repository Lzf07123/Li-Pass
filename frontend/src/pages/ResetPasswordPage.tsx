import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";
import { useToast } from "../hooks/useToast";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const toast = useToast();
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("两次输入的新密码不一致");
      return;
    }
    try {
      const result = await authApi.confirmPasswordReset({
        email,
        code,
        new_password: newPassword,
      });
      toast.success(result.message, {
        duration: 8000,
        action: {
          label: "去登录",
          onClick: () => navigate("/login"),
        },
      });
      setCode("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
    }
  }

  return (
    <AuthShell title="设置新密码" subtitle="输入发送到邮箱的 6 位验证码，并设置新密码">
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
        <label className="block">
          <span className="label">验证码</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="input"
            maxLength={6}
            inputMode="numeric"
            placeholder="6 位数字"
            required
          />
        </label>
        <label className="block">
          <span className="label">新密码</span>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="input"
            minLength={8}
            placeholder="至少 8 位"
            autoComplete="new-password"
            required
          />
        </label>
        <label className="block">
          <span className="label">确认新密码</span>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="input"
            minLength={8}
            autoComplete="new-password"
            required
          />
        </label>
        <button type="submit" className="btn btn-primary w-full">
          重置密码
        </button>
        <p className="text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
