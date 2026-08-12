import type {
  AppOut,
  ClientCreate,
  ClientBlockOut,
  ClientOut,
  ClientSecretOut,
  ConsentInfo,
  SessionOut,
  TotpSetup,
  TwoFaStatus,
  UserOut,
} from "./types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
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
  register: (data: { email: string; password: string; nickname: string }) =>
    api<UserOut>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),
  verifyEmail: (data: { email: string; code: string }) =>
    api<{ message: string }>("/api/v1/auth/email/verify", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    api<
      UserOut & {
        requires_2fa?: boolean;
        challenge_id?: string;
        methods?: string[];
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
};

export const meApi = {
  updateProfile: (data: { nickname?: string; avatar_url?: string | null }) =>
    api<UserOut>("/api/v1/me", { method: "PUT", body: JSON.stringify(data) }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api<{ message: string }>("/api/v1/me/password", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  bindPhone: (data: { phone: string }) =>
    api<UserOut>("/api/v1/me/phone/bind", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const sessionsApi = {
  list: () => api<SessionOut[]>("/api/v1/sessions"),
  revoke: (id: string) => api<void>(`/api/v1/sessions/${id}`, { method: "DELETE" }),
};

export const appsApi = {
  list: () => api<AppOut[]>("/api/v1/apps"),
  revoke: (clientId: string) =>
    api<void>(`/api/v1/apps/${clientId}`, {
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
  enableEmail: () =>
    api<{ message: string }>("/api/v1/me/2fa/email/enable", { method: "POST" }),
  disableEmail: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/2fa/email/disable", {
      method: "POST",
      body: JSON.stringify({ current_password }),
    }),
  totpSetup: () => api<TotpSetup>("/api/v1/me/2fa/totp/setup"),
  totpEnable: (code: string, secret: string) =>
    api<{ message: string; recovery_codes: string[] }>("/api/v1/me/2fa/totp/enable", {
      method: "POST",
      body: JSON.stringify({ code, secret }),
    }),
  totpDisable: (current_password: string) =>
    api<{ message: string }>("/api/v1/me/2fa/totp/disable", {
      method: "POST",
      body: JSON.stringify({ current_password }),
    }),
};
