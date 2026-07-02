import { useCallback, useEffect, useState } from "react";
import { api, HoldingProfilePublic } from "../api";
import { HoldingsSession, setHoldingsSession } from "../holdingsAuth";

type Mode = "login" | "register";

interface Props {
  onAuthenticated: (session: HoldingsSession) => void | Promise<void>;
}

export default function HoldingsAuthGate({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [profiles, setProfiles] = useState<HoldingProfilePublic[]>([]);

  const loadProfiles = useCallback(async () => {
    try {
      const list = await api.listHoldingProfiles();
      setProfiles(list);
    } catch {
      setProfiles([]);
    }
  }, []);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (mode === "register" && password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const res =
        mode === "register"
          ? await api.registerHoldingProfile(username.trim(), password)
          : await api.loginHoldingProfile(username.trim(), password);
      const session: HoldingsSession = {
        token: res.token,
        username: res.username,
        profileId: res.profile_id,
      };
      setHoldingsSession(session);
      await onAuthenticated(session);
      await loadProfiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="holdings-auth">
      <section className="holdings-auth-card">
        <h2 className="section-title">Your holdings profile</h2>
        <p className="holdings-auth-lead">
          Create a private profile with a password to save positions and return anytime. Only you can
          read your holdings — passwords can be reset from the server if you forget yours.
        </p>

        <div className="holdings-auth-tabs">
          <button
            type="button"
            className={`holdings-auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => {
              setMode("login");
              setError("");
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`holdings-auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => {
              setMode("register");
              setError("");
            }}
          >
            Create profile
          </button>
        </div>

        <form className="holdings-auth-form" onSubmit={submit}>
          <label className="holdings-field-label" htmlFor="holdings-username">
            Username
          </label>
          <input
            id="holdings-username"
            className="holdings-input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="3–32 letters, numbers, underscore"
            autoComplete="username"
            required
            minLength={3}
            maxLength={32}
          />

          <label className="holdings-field-label" htmlFor="holdings-password">
            Password
          </label>
          <input
            id="holdings-password"
            className="holdings-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            required
            minLength={8}
          />

          {mode === "register" && (
            <>
              <label className="holdings-field-label" htmlFor="holdings-confirm">
                Confirm password
              </label>
              <input
                id="holdings-confirm"
                className="holdings-input"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
              />
            </>
          )}

          {error && <p className="holdings-auth-error">{error}</p>}

          <button type="submit" className="btn btn-primary holdings-auth-submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "register" ? "Create profile & sign in" : "Sign in"}
          </button>
        </form>
      </section>

      <section className="holdings-profiles-list">
        <h2 className="section-title">Profiles on Shizu</h2>
        <p className="holdings-auth-lead">
          Usernames only — holdings data stays private to each profile.
        </p>
        {profiles.length === 0 ? (
          <p className="holdings-profiles-empty">No profiles yet. Be the first to create one.</p>
        ) : (
          <ul className="holdings-profiles-grid">
            {profiles.map((p) => (
              <li key={p.username} className="holdings-profile-chip">
                <span className="holdings-profile-name">{p.username}</span>
                <span className="holdings-profile-meta">
                  {p.holdings_count} position{p.holdings_count === 1 ? "" : "s"} · joined{" "}
                  {new Date(p.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
