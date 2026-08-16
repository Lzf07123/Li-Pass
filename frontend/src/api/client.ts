import type {
  AdminNotificationListOut,
  AdminSessionListOut,
  AdminStats,
  AdminSystemInfo,
  AdminUserOut,
  AppOut,
  AuditLogOut,
  BatchDeleteResult,
  BatchInviteResult,
  ClientCreate,
  ClientBlockOut,
  ClientOut,
  ClientSecretOut,
  ClientUpdate,
  ConsentInfo,
  Ip2regionUpdateStartResult,
  Ip2regionUpdateStatus,
  MessageListOut,
  RevokeSessionsResult,
  SendNotificationResult,
  SessionInfo,
  SessionOut,
  SiteSettings,
  StepUpStatus,
  TrustedDeviceOut,
  TotpSetup,
  TwoFaStatus,
  UserOut,
} from "./types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";
export const API_BASE_URL = BASE_URL;

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 401 && isSessionGuardedPath(path)) {
    // 会话被吊销/过期：通知全局监听器清空用户态并带 next 跳登录。
    // 登录/找回密码等认证端点自身的 401 不触发，避免误跳。
    window.dispatchEvent(new Event("lipass:unauthorized"));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    if (typeof body.detail === "string") {
      throw new Error(body.detail);
    }
    if (Array.isArray(body.detail)) {
      throw new Error(
        body.detail
          .map((item) => (item && typeof item === "object" ? String((item as { msg?: unknown }).msg ?? "") : String(item)))
          .filter(Boolean)
          .join("；")
      );
    }
    throw new Error(`请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

function isSessionGuardedPath(path: string): boolean {
  return (
    !path.startsWith("/api/v1/auth/") &&
    !path.startsWith("/oauth2/") &&
    !path.startsWith("/api/v1/oauth/logout-requests/")
  );
}

export const authApi = {
  inviteStatus: (token: string) =>
    api<{
      valid: boolean;
      email: string;
      email_taken: boolean;
      expires_at: string;
    }>(
      `/api/v1/auth/invite/status?token=${encodeURIComponent(token)}`,
    ),
  registerByInvite: (data: {
    token: string;
    nickname: string;
    password: string;
  }) =>
    api<{ message: string }>("/api/v1/auth/invite/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  register: (data: { email: string; password: string; nickname: string }) =>
    api<UserOut>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),
  registerStatus: () =>
    api<{ public_registration_enabled: boolean }>(
      "/api/v1/auth/register/status",
    ),
  verifyEmail: (data: { email: string; code: string }) =>
    api<{ message: string }>("/api/v1/auth/email/verify", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  resendVerifyEmail: (email: string) =>
    api<{ message: string }>("/api/v1/auth/email/verify/resend", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  login: (data: { email: string; password: string; remember_me?: boolean }) =>
    api<
      UserOut & {
        requires_2fa?: boolean;
        challenge_id?: string;
        methods?: string[];
        /** 登录时是否已向邮箱发送 2FA 验证码 */
        email_sent?: boolean;
        /** 邮件发送状态：sent / failed / rate_limited / skipped */
        email_status?: "sent" | "failed" | "rate_limited" | "skipped";
        /** 邮件限流剩余等待秒数（rate_limited 时展示用） */
        email_retry_after_seconds?: number;
      }
    >("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) }),
  logout: () =>
    api<{ redirect_to: string | null }>("/api/v1/auth/logout", {
      method: "POST",
    }),
  logoutLocal: () =>
    api<{ message: string }>("/api/v1/auth/logout/local", {
      method: "POST",
    }),
  me: () => api<UserOut>("/api/v1/me"),
  requestPasswordReset: (data: { email: string }) =>
    api<{ message: string }>("/api/v1/auth/password/reset", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  confirmPasswordReset: (data: { email: string; code: string; new_password: string }) =>
    api<{ message: string }>("/api/v1/auth/password/reset/confirm", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const consentApi = {
  info: (requestId: string) => api<ConsentInfo>(`/api/v1/consent/${requestId}`),
  approve: (requestId: string) =>
    api<{ redirect_url: string }>(`/api/v1/consent/${requestId}/approve`, {
      method: "POST",
    }),
  deny: (requestId: string) =>
    api<{ redirect_url: string }>(`/api/v1/consent/${requestId}/deny`, {
      method: "POST",
    }),
};

export const oauthApi = {
  logoutRequestInfo: (requestId: string) =>
    api<{ client_name: string }>(`/api/v1/oauth/logout-requests/${requestId}`),
  confirmLogoutRequest: (requestId: string) =>
    api<{ redirect_url: string }>(
      `/api/v1/oauth/logout-requests/${requestId}/confirm`,
      { method: "POST" }
    ),
  localOnlyLogoutRequest: (requestId: string) =>
    api<{ redirect_url: string }>(
      `/api/v1/oauth/logout-requests/${requestId}/local-only`,
      { method: "POST" }
    ),
};

export const adminClientsApi = {
  list: () => api<ClientOut[]>("/api/v1/admin/clients"),
  create: (data: ClientCreate) =>
    api<ClientSecretOut>("/api/v1/admin/clients", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  remove: (id: string, current_password?: string) =>
    api<void>(`/api/v1/admin/clients/${id}`, {
      method: "DELETE",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
  update: (id: string, data: ClientUpdate) =>
    api<ClientOut>(`/api/v1/admin/clients/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  resetSecret: (id: string, current_password?: string) =>
    api<ClientSecretOut>(`/api/v1/admin/clients/${id}/reset-secret`, {
      method: "POST",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
};

export interface SiteSettingsUpdate {
  public_registration_enabled?: boolean;
  ip2region_auto_update_enabled?: boolean;
  ip2region_update_interval_hours?: number;
}

export const adminSettingsApi = {
  get: () => api<SiteSettings>("/api/v1/admin/settings"),
  update: (data: SiteSettingsUpdate) =>
    api<SiteSettings>("/api/v1/admin/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  ip2regionUpdate: () =>
    api<Ip2regionUpdateStartResult>(
      "/api/v1/admin/settings/ip2region/update",
      {
        method: "POST",
      },
    ),
  ip2regionUpdateStatus: () =>
    api<Ip2regionUpdateStatus>(
      "/api/v1/admin/settings/ip2region/update/status",
      {
        method: "GET",
      },
    ),
};

export const adminSystemApi = {
  get: () => api<AdminSystemInfo>("/api/v1/admin/system"),
};

export const adminStatsApi = {
  get: (days = 30) => api<AdminStats>(`/api/v1/admin/stats?days=${days}`),
};

export const meApi = {
  sessionInfo: () => api<SessionInfo>("/api/v1/me/session"),
  updateProfile: (data: {
    nickname?: string;
    avatar_url?: string | null;
    email_notifications?: boolean;
  }) =>
    api<UserOut>("/api/v1/me", { method: "PUT", body: JSON.stringify(data) }),
  stepUpStatus: () => api<StepUpStatus>("/api/v1/me/step-up"),
  stepUpVerify: (password: string) =>
    api<StepUpStatus & { message: string }>("/api/v1/me/step-up", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  stepUpSend: () =>
    api<{ message: string }>("/api/v1/me/step-up/send", {
      method: "POST",
    }),
  changePassword: (data: {
    current_password?: string;
    new_password: string;
  }) =>
    api<{ message: string }>("/api/v1/me/password", {
      method: "POST",
      body: JSON.stringify({
        new_password: data.new_password,
        ...(data.current_password
          ? { current_password: data.current_password }
          : {}),
      }),
    }),
  deleteAccount: (
    current_password?: string,
    stepup_method?: string,
    stepup_code?: string,
  ) =>
    api<{ message: string }>("/api/v1/me/delete", {
      method: "POST",
      body: JSON.stringify({
        ...(current_password ? { current_password } : {}),
        ...(stepup_method ? { stepup_method } : {}),
        ...(stepup_code ? { stepup_code } : {}),
      }),
    }),
  sendPhoneBind: () =>
    api<{ message: string }>("/api/v1/me/phone/bind/send", {
      method: "POST",
    }),
  bindPhone: (data: { phone: string; code: string }) =>
    api<UserOut>("/api/v1/me/phone/bind", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<UserOut>("/api/v1/me/avatar", {
      method: "POST",
      body: form,
    });
  },
};

export const sessionsApi = {
  list: () => api<SessionOut[]>("/api/v1/sessions"),
  revoke: (id: string) => api<void>(`/api/v1/sessions/${id}`, { method: "DELETE" }),
  revokeAll: () =>
    api<{ revoked: number }>("/api/v1/sessions/revoke-all", { method: "POST" }),
};

export const appsApi = {
  list: () => api<AppOut[]>("/api/v1/apps"),
  revoke: (clientId: string) =>
    api<{
      logout_uri: string | null;
      /** 是否已向该网站的回程登出地址派发 logout_token */
      backchannel_notified: boolean;
      /** 该网站是否配置了回程登出地址 */
      backchannel_configured: boolean;
    }>(`/api/v1/apps/${clientId}`, { method: "DELETE" }),
};

export const adminBlocksApi = {
  list: (clientId: string) =>
    api<ClientBlockOut[]>(`/api/v1/admin/clients/${clientId}/blocks`),
  add: (clientId: string, data: { email: string; reason: string }) =>
    api<ClientBlockOut>(`/api/v1/admin/clients/${clientId}/blocks`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  remove: (clientId: string, blockId: string) =>
    api<void>(`/api/v1/admin/clients/${clientId}/blocks/${blockId}`, {
      method: "DELETE",
  }),
};

export const auth2faApi = {
  send: (challenge_id: string) =>
    api<{ message: string }>("/api/v1/auth/2fa/send", {
      method: "POST",
      body: JSON.stringify({ challenge_id }),
    }),
  verify: (
    challenge_id: string,
    method: string,
    code: string,
    trust_device: boolean = false,
  ) =>
    api<UserOut>("/api/v1/auth/2fa/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id, method, code, trust_device }),
    }),
};

export const trustedDevicesApi = {
  list: () => api<TrustedDeviceOut[]>("/api/v1/me/trusted-devices"),
  revoke: (id: string) =>
    api<void>(`/api/v1/me/trusted-devices/${id}`, { method: "DELETE" }),
};

export const twofaApi = {
  status: () => api<TwoFaStatus>("/api/v1/me/2fa/status"),
  enableEmail: (current_password?: string) =>
    api<{ message: string }>("/api/v1/me/2fa/email/enable", {
      method: "POST",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
  disableEmail: (current_password?: string) =>
    api<{ message: string }>("/api/v1/me/2fa/email/disable", {
      method: "POST",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
  totpSetup: () => api<TotpSetup>("/api/v1/me/2fa/totp/setup"),
  totpEnable: (code: string, secret: string, current_password?: string) =>
    api<{ message: string; recovery_codes: string[] }>("/api/v1/me/2fa/totp/enable", {
      method: "POST",
      body: JSON.stringify({
        code,
        secret,
        ...(current_password ? { current_password } : {}),
      }),
    }),
  totpDisable: (current_password?: string) =>
    api<{ message: string }>("/api/v1/me/2fa/totp/disable", {
      method: "POST",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
};

export const adminUsersApi = {
  list: (q = "", status = "", role = "") => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    if (role) params.set("role", role);
    const query = params.toString();
    return api<AdminUserOut[]>(
      `/api/v1/admin/users${query ? `?${query}` : ""}`,
    );
  },
  createAccount: (data: {
    email: string;
    nickname: string;
    password: string;
    role?: string;
    status?: string;
  }) =>
    api<AdminUserOut>("/api/v1/admin/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  invite: (data: { email: string; nickname?: string }) =>
    api<{ message: string }>("/api/v1/admin/users/invite", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  cancelInvite: (id: string) =>
    api<{ message: string }>(`/api/v1/admin/users/invites/${id}/cancel`, {
      method: "POST",
    }),
  resendInvite: (id: string) =>
    api<{ message: string }>(`/api/v1/admin/users/invites/${id}/resend`, {
      method: "POST",
    }),
  deleteInvite: (id: string) =>
    api<{ message: string }>(`/api/v1/admin/users/invites/${id}/delete`, {
      method: "POST",
    }),
  batchInvite: (emails: string[]) =>
    api<BatchInviteResult>("/api/v1/admin/users/batch/invite", {
      method: "POST",
      body: JSON.stringify({ emails }),
    }),
  batchUpdate: (
    ids: string[],
    data: { status?: string; role?: string },
    currentPassword?: string,
  ) =>
    api<{ updated: AdminUserOut[] }>("/api/v1/admin/users/batch", {
      method: "PATCH",
      body: JSON.stringify({
        user_ids: ids,
        ...data,
        ...(currentPassword ? { current_password: currentPassword } : {}),
      }),
    }),
  batchDelete: (
    ids: string[],
    current_password?: string,
    stepup_method?: string,
    stepup_code?: string,
  ) =>
    api<BatchDeleteResult>("/api/v1/admin/users/batch/delete", {
      method: "POST",
      body: JSON.stringify({
        user_ids: ids,
        ...(current_password ? { current_password } : {}),
        ...(stepup_method ? { stepup_method } : {}),
        ...(stepup_code ? { stepup_code } : {}),
      }),
    }),
  update: (
    id: string,
    data: { status?: string; role?: string },
    currentPassword?: string,
  ) =>
    api<AdminUserOut>(`/api/v1/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        ...data,
        ...(currentPassword ? { current_password: currentPassword } : {}),
      }),
    }),
  resetPassword: (
    id: string,
    new_password: string,
    current_password?: string,
  ) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/reset-password`, {
      method: "POST",
      body: JSON.stringify({
        new_password,
        ...(current_password ? { current_password } : {}),
      }),
    }),
  reset2fa: (id: string, current_password?: string) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/reset-2fa`, {
      method: "POST",
      body: JSON.stringify(current_password ? { current_password } : {}),
    }),
  deleteAccount: (
    id: string,
    current_password?: string,
    stepup_method?: string,
    stepup_code?: string,
  ) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/delete`, {
      method: "POST",
      body: JSON.stringify({
        ...(current_password ? { current_password } : {}),
        ...(stepup_method ? { stepup_method } : {}),
        ...(stepup_code ? { stepup_code } : {}),
      }),
    }),
};

export const adminSessionsApi = {
  list: (q = "", offset = 0, limit = 100) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    params.set("offset", String(offset));
    params.set("limit", String(limit));
    const query = params.toString();
    return api<AdminSessionListOut>(`/api/v1/admin/sessions?${query}`);
  },
  revoke: (id: string) =>
    api<void>(`/api/v1/admin/sessions/${id}`, { method: "DELETE" }),
  revokeMany: (ids: string[]) =>
    api<RevokeSessionsResult>("/api/v1/admin/sessions/batch-revoke", {
      method: "POST",
      body: JSON.stringify({ session_ids: ids }),
    }),
  revokeAll: () =>
    api<RevokeSessionsResult>("/api/v1/admin/sessions/revoke-all", {
      method: "POST",
    }),
};

export const adminNotificationsApi = {
  create: (data: {
    title: string;
    body: string;
    in_site: boolean;
    email: boolean;
    user_ids?: string[];
  }) =>
    api<SendNotificationResult>("/api/v1/admin/notifications", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  list: (offset = 0, limit = 100) =>
    api<AdminNotificationListOut>(
      `/api/v1/admin/notifications?offset=${offset}&limit=${limit}`
    ),
  recall: (id: string) =>
    api<{ recalled: number }>(
      `/api/v1/admin/notifications/${id}/recall`,
      { method: "POST" }
    ),
};

export const userMessagesApi = {
  list: (offset = 0, limit = 100) =>
    api<MessageListOut>(
      `/api/v1/me/messages?offset=${offset}&limit=${limit}`
    ),
  unreadCount: () =>
    api<{ unread: number }>("/api/v1/me/messages/unread-count"),
  markRead: (id: string) =>
    api<void>(`/api/v1/me/messages/${id}/read`, { method: "POST" }),
  markAllRead: () =>
    api<{ updated: number }>("/api/v1/me/messages/read-all", {
      method: "POST",
    }),
  remove: (id: string) =>
    api<void>(`/api/v1/me/messages/${id}`, { method: "DELETE" }),
};

export const adminAuditApi = {
  list: (params: AuditQuery = {}) => {
    const search = new URLSearchParams();
    if (params.category) search.set("category", params.category);
    if (params.action) search.set("action", params.action);
    if (params.actor_id) search.set("actor_id", params.actor_id);
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
    search.set("limit", String(params.limit ?? 100));
    search.set("offset", String(params.offset ?? 0));
    return api<AuditLogOut[]>(`/api/v1/admin/audit-logs?${search.toString()}`);
  },
};

export interface AuditQuery {
  category?: string;
  action?: string;
  actor_id?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}
