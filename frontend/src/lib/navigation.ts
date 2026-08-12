import { API_BASE_URL } from "../api/client";

/** 校验 OAuth next 参数：仅放行同源或 API 同源的相对/绝对地址 */
export function isSafeNext(value: string | null): boolean {
  if (!value) return false;
  // 相对路径放行（排除 //host 协议相对地址）
  if (value.startsWith("/") && !value.startsWith("//")) return true;
  try {
    const target = new URL(value, window.location.origin);
    const apiOrigin = API_BASE_URL
      ? new URL(API_BASE_URL, window.location.origin).origin
      : window.location.origin;
    return (
      (target.protocol === "http:" || target.protocol === "https:") &&
      (target.origin === window.location.origin || target.origin === apiOrigin)
    );
  } catch {
    return false;
  }
}
