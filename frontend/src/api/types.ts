export interface UserOut {
  id: string;
  email: string;
  nickname: string;
  email_verified: boolean;
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
  email: string;
  nickname: string;
  phone: string | null;
  email_verified: boolean;
  role: string;
  status: string;
  created_at: string;
}

export interface AuditLogOut {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}
