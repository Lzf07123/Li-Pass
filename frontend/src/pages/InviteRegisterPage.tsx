import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";
import { AsyncButton } from "../components/AsyncButton";
import { AuthShell } from "../components/AuthShell";
import { Notice } from "../components/Notice";
import { PasswordInput } from "../components/PasswordInput";
import { PasswordStrength } from "../components/PasswordStrength";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useToast } from "../hooks/useToast";

export function InviteRegisterPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [checking, setChecking] = useState(token !== "");
  const [statusError, setStatusError] = useState("");
  const [inviteInfo, setInviteInfo] = useState<{
    email: string;
    email_taken: boolean;
  } | null>(null);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    authApi
      .inviteStatus(token)
      .then((info) => {
        if (cancelled) return;
        setInviteInfo({ email: info.email, email_taken: info.email_taken });
      })
      .catch((err) => {
        if (cancelled) return;
        setStatusError(
          err instanceof Error ? err.message : "邀请链接无效",
        );
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const submitAction = useAsyncAction(
    async (nickname: string, password: string) => {
      const result = await authApi.registerByInvite({
        token,
        nickname,
        password,
      });
      toast.success(result.message);
      navigate("/login");
    },
    {
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "注册失败"),
    },
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 8) {
      toast.error("密码至少 8 位");
      return;
    }
    if (password !== confirmPassword) {
      toast.error("两次输入的密码不一致");
      return;
    }
    await submitAction.run(nickname, password);
  }

  if (!token) {
    return (
      <AuthShell title="受邀注册" subtitle="请使用管理员发送的邀请链接完成注册">
        <Notice intent="error">邀请链接无效：缺少令牌参数。</Notice>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </AuthShell>
    );
  }

  if (checking) {
    return (
      <AuthShell title="受邀注册" subtitle="正在校验邀请链接…">
        <div
          className="shimmer h-40 w-full rounded-xl"
          aria-busy="true"
          aria-label="正在校验邀请链接"
        />
      </AuthShell>
    );
  }

  if (statusError) {
    return (
      <AuthShell title="受邀注册" subtitle="邀请链接校验失败">
        <Notice intent="error">{statusError}</Notice>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="btn-link">
            返回登录
          </Link>
        </p>
      </AuthShell>
    );
  }

  if (inviteInfo?.email_taken) {
    return (
      <AuthShell title="受邀注册" subtitle="该邮箱已有账号">
        <Notice intent="info">
          邀请邮箱 {inviteInfo.email} 已注册账号，请直接登录。
        </Notice>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="btn-link">
            去登录
          </Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="受邀注册"
      subtitle={
        inviteInfo
          ? `邀请发送至 ${inviteInfo.email}，设置密码即可激活账号`
          : "你已被邀请加入，设置密码即可激活账号"
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="label">昵称</span>
          <input
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            className="input"
            autoComplete="nickname"
            required
            autoFocus
          />
        </label>
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
        <PasswordStrength password={password} />
        <label className="block">
          <span className="label">确认密码</span>
          <PasswordInput
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="input"
            minLength={8}
            autoComplete="new-password"
            required
          />
        </label>
        <AsyncButton
          type="submit"
          status={submitAction.status}
          className="btn btn-primary w-full"
        >
          完成注册
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
