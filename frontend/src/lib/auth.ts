const TOKEN_KEY = "catastro_token";
const USER_KEY = "catastro_user";

export type AuthUser = {
  id: string;
  email: string;
  username?: string | null;
  first_name: string;
  last_name: string;
  document_number?: string | null;
  professional_reg?: string | null;
  auxiliary_email?: string | null;
  roles: string[];
  must_have_professional_reg: boolean;
  must_change_password?: boolean;
};

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}
