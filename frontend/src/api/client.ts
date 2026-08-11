import type {
  ClientCreate,
  ClientOut,
  ClientSecretOut,
  ConsentInfo,
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
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `请求失败：${response.status}`);
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
    api<UserOut>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) }),
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
