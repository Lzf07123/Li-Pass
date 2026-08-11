export interface UserOut {
  id: string;
  email: string;
  nickname: string;
  email_verified: boolean;
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
  redirect_uris: string[];
  scopes?: string[];
  require_consent_every_time?: boolean;
  public?: boolean;
}

export interface ClientSecretOut {
  client: ClientOut;
  client_secret: string | null;
}
