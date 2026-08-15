import { usePasswordStrength } from "../hooks/usePasswordStrength";

const SEGMENT_STYLES: Record<string, string> = {
  weak: "bg-destructive",
  medium: "bg-warning",
  strong: "bg-success",
};

const TEXT_STYLES: Record<string, string> = {
  weak: "text-destructive",
  medium: "text-warning",
  strong: "text-success",
};

/**
 * 密码强度指示：三段色条 + 弱/中/强文案；密码为空时不渲染。
 */
export function PasswordStrength({ password }: { password: string }) {
  const strength = usePasswordStrength(password);
  if (!password) return null;
  const activeSegments =
    strength.level === "weak" ? 1 : strength.level === "medium" ? 2 : 3;
  return (
    <div className="mt-1.5 flex items-center gap-2" aria-live="polite">
      <div className="flex flex-1 gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className={`h-1.5 flex-1 rounded-full ${
              index < activeSegments
                ? SEGMENT_STYLES[strength.level]
                : "bg-surface-2"
            }`}
          />
        ))}
      </div>
      <span className={`text-xs ${TEXT_STYLES[strength.level]}`}>
        密码强度：{strength.label}
      </span>
    </div>
  );
}
