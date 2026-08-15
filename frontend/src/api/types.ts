export interface UserOut {
  id: string;
  email: string;
  nickname: string;
  email_verified: boolean;
  avatar_url: string | null;
  phone: string | null;
  email_notifications: boolean;
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
  post_logout_redirect_uris: string[];
  backchannel_logout_uri: string | null;
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
  post_logout_redirect_uris?: string[];
  backchannel_logout_uri?: string | null;
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
  post_logout_redirect_uris?: string[];
  backchannel_logout_uri?: string | null;
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
  ip_location: string | null;
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

export interface AdminNotificationOut {
  id: string;
  title: string;
  in_site: boolean;
  email: boolean;
  recipient_count: number;
  email_sent: number;
  email_failed: number;
  recalled_at: string | null;
  created_at: string;
  sender_email: string | null;
  sender_nickname: string | null;
}

export interface AdminNotificationListOut {
  items: AdminNotificationOut[];
  total: number;
}

export interface SendNotificationResult {
  id: string;
  recipient_count: number;
  skipped?: number;
  email_sent: number;
  email_failed: number;
}

export interface MessageOut {
  id: string;
  title: string;
  body: string;
  sent_at: string;
  read: boolean;
}

export interface MessageListOut {
  items: MessageOut[];
  total: number;
  unread: number;
}

export interface RevokeSessionsResult {
  revoked: number;
  skipped?: number;
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

export interface StepUpStatus {
  active: boolean;
  window_minutes: number;
  expires_in_seconds: number;
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
  ip2region: Ip2regionStatus;
}

export interface Ip2regionStatus {
  version: string | null;
  data_updated_at: string | null;
  v4_ready: boolean;
  v6_ready: boolean;
  auto_update_enabled: boolean;
  update_interval_hours: number;
}

export interface Ip2regionUpdateStatus {
  state: "idle" | "running" | "success" | "error";
  stage:
    | "idle"
    | "checking"
    | "downloading_v4"
    | "downloading_v6"
    | "installing";
  downloaded_bytes: number;
  total_bytes: number;
  percent: number;
  version: string | null;
  changed: boolean | null;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Ip2regionUpdateStartResult {
  started: boolean;
  status: Ip2regionUpdateStatus;
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
  ip_location: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminSystemInfo {
  collected_at: string;
  app: {
    name: string;
    environment: string;
    python_version: string;
    fastapi_version: string;
  };
  host: {
    hostname: string;
    system: string;
    release: string;
    machine: string;
    platform: string;
    cpu_cores: number | null;
  };
  load: {
    avg_1m: number | null;
    avg_5m: number | null;
    avg_15m: number | null;
  };
  memory: {
    total_bytes: number;
    used_bytes: number;
    available_bytes: number;
    percent: number;
    process_rss_bytes: number;
  };
  disk: {
    path: string;
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    percent: number;
  };
  uptime: {
    system_seconds: number | null;
    process_seconds: number;
  };
  process: {
    pid: number;
    python_implementation: string;
  };
  services: {
    database: string;
    redis: string;
  };
}

export interface AdminStatsOverview {
  total_users: number;
  active_users: number;
  disabled_users: number;
  admins: number;
  verified_users: number;
  online_sessions: number;
  total_logins: number;
}

export interface AdminStatsDailyPoint {
  date: string;
  logins: number;
  login_users: number;
  registrations: number;
}

export interface AdminStatsAuthMethod {
  method: string;
  count: number;
}

export interface AdminStatsRegion {
  region: string;
  count: number;
}

export interface AdminStatsMapRegion {
  name: string;
  value: number;
}

export interface AdminStatsRegionsOther {
  overseas: number;
  internal: number;
  unknown: number;
}

export interface AdminStats {
  generated_at: string;
  timezone: string;
  days: number;
  overview: AdminStatsOverview;
  daily: AdminStatsDailyPoint[];
  auth_methods: AdminStatsAuthMethod[];
  regions: AdminStatsRegion[];
  regions_map: AdminStatsMapRegion[];
  regions_other: AdminStatsRegionsOther;
}
