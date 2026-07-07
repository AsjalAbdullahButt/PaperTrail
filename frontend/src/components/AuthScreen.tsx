"use client";

import { useState, type CSSProperties, type FormEvent } from "react";
import { ApiError, login, register } from "@/lib/api";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

/** Sign-in / register card shown when the user has no valid token.
 *
 * On success, api.login/api.register store the token and broadcast an auth
 * change, so the app switches automatically; onAuthed is an optional hook. */
export default function AuthScreen({ onAuthed }: { onAuthed?: () => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      onAuthed?.();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  const inputStyle: CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    borderRadius: 12,
    background: "var(--seg-bg)",
    border: "1px solid var(--card-border)",
    color: "var(--text)",
    fontFamily: "inherit",
    fontSize: 15,
    outline: "none",
  };

  return (
    <div
      style={{
        minHeight: "70vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginTop: 40,
      }}
    >
      <form
        onSubmit={handleSubmit}
        aria-label={mode === "login" ? "Sign in" : "Create account"}
        style={{
          width: "100%",
          maxWidth: 400,
          padding: "34px 32px",
          borderRadius: 22,
          background: "var(--card-bg)",
          border: "1px solid var(--card-border)",
          backdropFilter: "blur(22px) saturate(150%)",
          WebkitBackdropFilter: "blur(22px) saturate(150%)",
          boxShadow: "0 18px 50px var(--cardShadow)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 6 }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 9,
              background: ACCENT_GRADIENT,
              boxShadow: "0 4px 14px var(--accentGlow)",
            }}
          />
          <span style={{ fontWeight: 800, fontSize: 20, letterSpacing: "-.02em", color: "var(--text)" }}>
            PaperTrail
          </span>
        </div>
        <h1 style={{ margin: "10px 0 4px", fontSize: 22, fontWeight: 700, color: "var(--text)" }}>
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h1>
        <p style={{ margin: "0 0 22px", fontSize: 14, color: "var(--muted)" }}>
          {mode === "login"
            ? "Sign in to search your documents."
            : "Register to start uploading and querying documents."}
        </p>

        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ ...inputStyle, marginTop: 6 }}
          />
        </label>
        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--muted)", margin: "14px 0 6px" }}>
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ ...inputStyle, marginTop: 6 }}
          />
        </label>
        {mode === "register" && (
          <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--muted)" }}>
            At least 8 characters.
          </p>
        )}

        {error && (
          <div
            role="alert"
            style={{
              marginTop: 16,
              padding: "10px 14px",
              borderRadius: 12,
              fontSize: 13.5,
              color: "#ff8a80",
              background: "rgba(255,80,80,.10)",
              border: "1px solid rgba(255,120,120,.35)",
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          style={{
            width: "100%",
            marginTop: 20,
            padding: "13px 20px",
            borderRadius: 14,
            border: "none",
            cursor: busy ? "default" : "pointer",
            fontFamily: "inherit",
            fontWeight: 700,
            fontSize: 15,
            color: "var(--onAccent)",
            background: ACCENT_GRADIENT,
            boxShadow: "0 4px 14px var(--accentGlow)",
            opacity: busy ? 0.75 : 1,
          }}
        >
          {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        <p style={{ margin: "18px 0 0", fontSize: 13.5, color: "var(--muted)", textAlign: "center" }}>
          {mode === "login" ? "No account yet? " : "Already have an account? "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            style={{
              border: "none",
              background: "none",
              padding: 0,
              cursor: "pointer",
              fontFamily: "inherit",
              fontSize: 13.5,
              fontWeight: 700,
              color: "var(--accent)",
            }}
          >
            {mode === "login" ? "Create one" : "Sign in"}
          </button>
        </p>
      </form>
    </div>
  );
}
