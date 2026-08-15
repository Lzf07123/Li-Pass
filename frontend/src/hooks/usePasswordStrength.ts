export interface PasswordStrength {
  score: number;
  level: "weak" | "medium" | "strong";
  label: "弱" | "中" | "强";
}

export function assessPasswordStrength(password: string): PasswordStrength {
  const checks = [
    password.length >= 8,
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ];
  const score = checks.filter(Boolean).length;
  let level: PasswordStrength["level"];
  let label: PasswordStrength["label"];
  if (score >= 4) {
    level = "strong";
    label = "强";
  } else if (score >= 3) {
    level = "medium";
    label = "中";
  } else {
    level = "weak";
    label = "弱";
  }
  return { score, level, label };
}

export function usePasswordStrength(password: string): PasswordStrength {
  return assessPasswordStrength(password);
}
