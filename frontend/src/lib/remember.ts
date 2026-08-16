const ACCOUNT_KEY = "lipass.remember.account";
// 历史版本的「记住密码」曾把明文密码写入此键；自 2026-08 起移除该功能，
// 持久化时顺带清理存量数据，避免旧密码继续滞留 localStorage。
const LEGACY_PASSWORD_KEY = "lipass.remember.password";

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getRememberedAccount(): string | null {
  return read(ACCOUNT_KEY);
}

/**
 * 仅登录成功后按勾选状态保存账号；取消勾选即清除。
 * 明文密码不再落盘（同源 XSS/共享设备可读风险），请使用浏览器密码管理器。
 */
export function persistRememberedAccount(
  email: string,
  rememberAccount: boolean,
): void {
  try {
    if (rememberAccount) {
      window.localStorage.setItem(ACCOUNT_KEY, email);
    } else {
      window.localStorage.removeItem(ACCOUNT_KEY);
    }
    window.localStorage.removeItem(LEGACY_PASSWORD_KEY);
  } catch {
    // 隐私模式/存储被禁用时静默降级：不记住，但登录流程不受影响。
  }
}
