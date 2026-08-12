import type {
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
  SessionOut,
  SiteSettings,
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

export const authApi = {
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
  logout: () => api<void>("/api/v1/auth/logout", { method: "POST" }),
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

export const adminClientsApi = {
  list: () => api<ClientOut[]>("/api/v1/admin/clients"),
  create: (data: ClientCreate) =>
    api<ClientSecretOut>("/api/v1/admin/clients", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  remove: (id: string) =>
    api<void>(`/api/v1/admin/clients/${id}`, {
      method: "DELETE",
    }),
  update: (id: string, data: ClientUpdate) =>
    api<ClientOut>(`/api/v1/admin/clients/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  resetSecret: (id: string) =>
    api<ClientSecretOut>(`/api/v1/admin/clients/${id}/reset-secret`, {
      method: "POST",
    }),
};

export const adminSettingsApi = {
  get: () => api<SiteSettings>("/api/v1/admin/settings"),
  update: (data: SiteSettings) =>
    api<SiteSettings>("/api/v1/admin/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

export const meApi = {
  updateProfile: (data: { nickname?: string; avatar_url?: string | null }) =>
    api<UserOut>("/api/v1/me", { method: "PUT", body: JSON.stringify(data) }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api<{ message: string }>("/api/v1/me/password", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteAccount: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/delete", {
      method: "POST",
      body: JSON.stringify({ current_password }),
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
};

export const appsApi = {
  list: () => api<AppOut[]>("/api/v1/apps"),
  revoke: (clientId: string) =>
    api<{ logout_uri: string | null }>(`/api/v1/apps/${clientId}`, {
      method: "DELETE",
    }),
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
  verify: (challenge_id: string, method: string, code: string) =>
    api<UserOut>("/api/v1/auth/2fa/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id, method, code }),
    }),
};

export const twofaApi = {
  status: () => api<TwoFaStatus>("/api/v1/me/2fa/status"),
  enableEmail: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/2fa/email/enable", {
      method: "POST",
      body: JSON.stringify({ current_password }),
    }),
  disableEmail: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/2fa/email/disable", {
      method: "POST",
      body: JSON.stringify({ current_password }),
    }),
  totpSetup: () => api<TotpSetup>("/api/v1/me/2fa/totp/setup"),
  totpEnable: (code: string, secret: string, current_password: string) =>
    api<{ message: string; recovery_codes: string[] }>("/api/v1/me/2fa/totp/enable", {
      method: "POST",
      body: JSON.stringify({ code, secret, current_password }),
    }),
  totpDisable: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/2fa/totp/disable", {
      method: "POST",
      body: JSON.stringify({ current_password }),
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
  ) =>
    api<{ updated: AdminUserOut[] }>("/api/v1/admin/users/batch", {
      method: "PATCH",
      body: JSON.stringify({ user_ids: ids, ...data }),
    }),
  batchDelete: (ids: string[], current_password: string) =>
    api<BatchDeleteResult>("/api/v1/admin/users/batch/delete", {
      method: "POST",
      body: JSON.stringify({ user_ids: ids, current_password }),
    }),
  update: (id: string, data: { status?: string; role?: string }) =>
    api<AdminUserOut>(`/api/v1/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  resetPassword: (id: string, new_password: string) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/reset-password`, {
      method: "POST",
      body: JSON.stringify({ new_password }),
    }),
  reset2fa: (id: string) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/reset-2fa`, {
      method: "POST",
    }),
  deleteAccount: (id: string, current_password: string) =>
    api<{ message: string }>(`/api/v1/admin/users/${id}/delete`, {
      method: "POST",
      body: JSON.stringify({ current_password }),
    }),
};

export const adminAuditApi = {
  list: (limit = 100) => api<AuditLogOut[]>(`/api/v1/admin/audit-logs?limit=${limit}`),
};
