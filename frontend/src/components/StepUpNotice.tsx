/**
 * step-up 复核窗口内的提示条：信任但不唬人，沿用 notice 视觉语言。
 */
export function StepUpNotice({
  expiresInSeconds,
}: {
  expiresInSeconds: number;
}) {
  const minutes = Math.max(1, Math.ceil(expiresInSeconds / 60));
  return (
    <div className="notice notice-info" role="status">
      <span className="notice-icon" aria-hidden="true">
        i
      </span>
      30 分钟内已通过身份复核（剩余约 {minutes} 分钟），无需再次输入密码
    </div>
  );
}
