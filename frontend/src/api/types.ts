export interface UserOut {
  id: string;
  email: string;
  nickname: string;
  email_verified: boolean;
  avatar_url: string | null;
  phone: string | null;
  role: string;
  status: string;
}

export interface ConsentInfo {
  request_id: string;
  client: { name: string; logo_url: string | null; description: string };
  scopes: string[];
}

export interface ClientOut {
  id: string;
  client_id: string;
  name: string;
  description: string;
  logo_url: string | null;
  home_url: string | null;
  logout_uri: string | null;
  redirect_uris: string[];
  scopes: string[];
  require_consent_every_time: boolean;
  is_active: boolean;
  has_secret: boolean;
  created_at: string;
}

export interface ClientCreate {
  name: string;
  description?: string;
  logo_url?: string | null;
  home_url?: string | null;
  logout_uri?: string | null;
  redirect_uris: string[];
  scopes?: string[];
  require_consent_every_time?: boolean;
  public?: boolean;
}

export interface ClientUpdate {
  name?: string;
  description?: string;
  logo_url?: string | null;
  home_url?: string | null;
  logout_uri?: string | null;
  redirect_uris?: string[];
  scopes?: string[];
  require_consent_every_time?: boolean;
  is_active?: boolean;
}

export interface ClientSecretOut {
  client: ClientOut;
  client_secret: string | null;
}

export interface SessionOut {
  id: string;
  device_name: string;
  ip: string;
  user_agent: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
}

export interface AdminSessionUserOut {
  id: string;
  email: string;
  nickname: string | null;
  role: string;
  status: string;
}

export interface AdminSessionOut {
  id: string;
  user: AdminSessionUserOut;
  auth_method: string;
  device_name: string;
  ip: string;
  user_agent: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
}

export interface AdminSessionListOut {
  items: AdminSessionOut[];
  total: number;
}

export interface AppOut {
  client_id: string;
  name: string;
  description: string;
  logo_url: string | null;
  home_url: string | null;
}

export interface ClientBlockOut {
  id: string;
  user_id: string | null;
  email: string | null;
  reason: string;
  created_at: string;
}

export interface TwoFaStatus {
  email_otp_enabled: boolean;
  totp_enabled: boolean;
  recovery_codes_remaining: number;
}

export interface TotpSetup {
  secret: string;
  otpauth_uri: string;
  qr_data_url: string;
}

export interface AdminUserOut {
  id: string;
  kind: "user" | "invite";
  email: string;
  nickname: string | null;
  phone: string | null;
  email_verified: boolean;
  role: string | null;
  status: string;
  created_at: string;
  expires_at: string | null;
  used_at?: string | null;
  cancelled_at?: string | null;
}

export interface BatchInviteResult {
  invited: string[];
  skipped: { email: string; reason: string }[];
  failed: { email: string; reason: string }[];
}

export interface BatchDeleteResult {
  message: string;
  deleted: { id: string; email: string }[];
}

export interface SiteSettings {
  public_registration_enabled: boolean;
}

export interface AuditLogOut {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  category: string | null;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}
