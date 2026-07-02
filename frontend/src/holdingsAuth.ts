const TOKEN_KEY = "holdings_auth_token";
const USER_KEY = "holdings_auth_user";
const PROFILE_KEY = "holdings_auth_profile_id";

export interface HoldingsSession {
  token: string;
  username: string;
  profileId: number;
}

export function getHoldingsSession(): HoldingsSession | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const username = sessionStorage.getItem(USER_KEY);
  const profileId = sessionStorage.getItem(PROFILE_KEY);
  if (!token || !username || !profileId) return null;
  const id = Number(profileId);
  if (!Number.isFinite(id)) return null;
  return { token, username, profileId: id };
}

export function setHoldingsSession(session: HoldingsSession | null): void {
  if (!session) {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(PROFILE_KEY);
    return;
  }
  sessionStorage.setItem(TOKEN_KEY, session.token);
  sessionStorage.setItem(USER_KEY, session.username);
  sessionStorage.setItem(PROFILE_KEY, String(session.profileId));
}

export function holdingsAuthHeaders(): Record<string, string> {
  const session = getHoldingsSession();
  if (!session) return {};
  return { Authorization: `Bearer ${session.token}` };
}
