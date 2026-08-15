const ACCOUNT_KEY = "lipass.remember.account";
const PASSWORD_KEY = "lipass.remember.password";

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

export function getRememberedPassword(): string | null {
  return read(PASSWORD_KEY);
}

/**
 * 仅登录成功后按勾选状态落盘；取消勾选即清除对应键。
 * 「记住密码」隐含「记住账号」，密码明文存 localStorage，
 * 安全权衡见 docs/superpowers/specs/2026-08-16-account-ux-security-improvements-design.md。
 */
export function persistRememberedCredentials(
  email: string,
  password: string,
  rememberAccount: boolean,
  rememberPassword: boolean,
): void {
  try {
    if (rememberAccount || rememberPassword) {
      window.localStorage.setItem(ACCOUNT_KEY, email);
    } else {
      window.localStorage.removeItem(ACCOUNT_KEY);
    }
    if (rememberPassword) {
      window.localStorage.setItem(ACCOUNT_KEY, email);
      window.localStorage.setItem(PASSWORD_KEY, password);
    } else {
      window.localStorage.removeItem(PASSWORD_KEY);
    }
  } catch {
    // 隐私模式/存储被禁用时静默降级：不记住，但登录流程不受影响。
  }
}
