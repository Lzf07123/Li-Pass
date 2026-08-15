import { useEffect, useState } from "react";

import { meApi } from "../api/client";
import type { AsyncStatus } from "../hooks/useAsyncAction";
import { AsyncButton } from "./AsyncButton";
import { PasswordInput } from "./PasswordInput";

const METHOD_LABELS: Record<string, string> = {
  email_otp: "邮箱验证码",
  totp: "认证器动态码（TOTP）",
};

export interface StepUp2faPayload {
  current_password: string;
  stepup_method: string;
  stepup_code: string;
}

/**
 * 注销/删除账号等高危操作的「密码 + 任意 2FA」复核表单。
 * 邮箱验证码支持一键发送（60 秒冷却）；TOTP 直接输入动态码。
 */
export function StepUp2faForm({
  emailOtpEnabled,
  totpEnabled,
  submitLabel,
  status,
  serverError,
  onSubmit,
}: {
  emailOtpEnabled: boolean;
  totpEnabled: boolean;
  submitLabel: string;
  status?: AsyncStatus;
  serverError?: string | null;
  onSubmit: (payload: StepUp2faPayload) => void;
}) {
  const methods = [
    emailOtpEnabled ? "email_otp" : null,
    totpEnabled ? "totp" : null,
  ].filter((item): item is string => item !== null);
  const [password, setPassword] = useState("");
  const [method, setMethod] = useState(
    methods.includes("email_otp") ? "email_otp" : methods[0] ?? "",
  );
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sendStatus, setSendStatus] = useState<AsyncStatus>("idle");
  const [codeSent, setCodeSent] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setTimeout(() => setCountdown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  async function sendCode() {
    if (sendStatus === "pending" || countdown > 0) return;
    setSendStatus("pending");
    setError(null);
    try {
      await meApi.stepUpSend();
      setCodeSent(true);
      setCountdown(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证码发送失败");
    } finally {
      setSendStatus("idle");
    }
  }

  function submit() {
    if (!password.trim()) {
      setError("请输入当前密码");
      return;
    }
    if (!method) {
      setError("未启用任何二次验证方式，无法执行此操作");
      return;
    }
    if (!code.trim()) {
      setError("请输入验证码");
      return;
    }
    onSubmit({
      current_password: password,
      stepup_method: method,
      stepup_code: code.trim(),
    });
  }

  const shownError = serverError ?? error;

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="label">当前密码</span>
        <PasswordInput
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setError(null);
          }}
          className="input"
          autoComplete="current-password"
          autoFocus
          required
        />
      </label>
      <fieldset className="space-y-2">
        <legend className="label">二次验证方式</legend>
        {methods.map((item) => (
          <label
            key={item}
            className="flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm transition-colors border-border text-foreground hover:bg-surface-2 data-[checked=true]:border-primary data-[checked=true]:bg-primary-soft"
            data-checked={method === item}
          >
            <input
              type="radio"
              name="stepup-method"
              value={item}
              checked={method === item}
              onChange={(e) => {
                setMethod(e.target.value);
                setError(null);
              }}
              className="accent-primary"
            />
            {METHOD_LABELS[item] ?? item}
          </label>
        ))}
      </fieldset>
      <label className="block">
        <span className="label">验证码</span>
        <div className="flex gap-2">
          <input
            value={code}
            onChange={(e) => {
              setCode(e.target.value);
              setError(null);
            }}
            className="input flex-1"
            inputMode={method === "email_otp" ? "numeric" : "text"}
            maxLength={method === "totp" ? 8 : 6}
            autoComplete="one-time-code"
            required
          />
          {method === "email_otp" && (
            <AsyncButton
              type="button"
              status={sendStatus}
              onClick={() => void sendCode()}
              disabled={countdown > 0}
              className="btn btn-secondary min-w-28 whitespace-nowrap"
            >
              {countdown > 0
                ? `重新发送（${countdown}s）`
                : codeSent
                  ? "重新发送"
                  : "获取验证码"}
            </AsyncButton>
          )}
        </div>
      </label>
      {shownError && (
        <p role="alert" className="text-xs text-destructive">
          {shownError}
        </p>
      )}
      <AsyncButton
        type="button"
        status={status ?? "idle"}
        className="btn btn-danger w-full"
        onClick={submit}
      >
        {submitLabel}
      </AsyncButton>
    </div>
  );
}
