import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthShell } from "../components/AuthShell";

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await authApi.register({ email, nickname, password });
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    }
  }

  return (
    <AuthShell title="注册 Portal OSS 账号" subtitle="一个账号，登录所有授权网站">
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
          <span className="label">昵称</span>
          <input
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            className="input"
            autoComplete="nickname"
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
            minLength={8}
            autoComplete="new-password"
            placeholder="至少 8 位"
            required
          />
        </label>
        {error && (
          <p className="alert alert-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary w-full">
          注册
        </button>
        <p className="text-center text-sm text-muted">
          已有账号？{" "}
          <Link to="/login" className="btn-link">
            去登录
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
