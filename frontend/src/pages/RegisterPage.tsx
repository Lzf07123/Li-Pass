import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import { AuthSkeleton } from "../components/AuthSkeleton";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";
import { APP_NAME } from "../lib/brand";

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [registrationStatus, setRegistrationStatus] = useState<
    "loading" | "open" | "closed"
  >("loading");
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    authApi
      .registerStatus()
      .then((result) => {
        if (!cancelled) {
          setRegistrationStatus(
            result.public_registration_enabled ? "open" : "closed",
          );
        }
      })
      .catch(() => {
        // 状态接口不可用时按“开放注册”处理，后端仍会强制执行开关。
        if (!cancelled) setRegistrationStatus("open");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submitAction = useAsyncAction(
    async (email: string, nickname: string, password: string) => {
      await authApi.register({ email, nickname, password });
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "注册失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitAction.run(email, nickname, password);
  }

  if (registrationStatus === "loading") {
    return <AuthSkeleton />;
  }

  if (registrationStatus === "closed") {
    return (
      <AuthShell title={`注册 ${APP_NAME} 账号`} subtitle="一个账号，登录所有授权网站">
        <Notice intent="warning">注册渠道暂时关闭，只接收邀请注册</Notice>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title={`注册 ${APP_NAME} 账号`} subtitle="一个账号，登录所有授权网站">
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
        <div>
          <label className="block">
            <span className="label">密码</span>
            <PasswordInput
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              minLength={8}
              autoComplete="new-password"
              placeholder="至少 8 位"
              required
            />
          </label>
          <p className="mt-1.5 text-xs text-muted">
            建议使用 8 位以上，并混合大小写字母、数字和符号。
          </p>
        </div>
        <AsyncButton
          type="submit"
          status={submitAction.status}
          className="btn btn-primary w-full"
        >
          注册
        </AsyncButton>
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
