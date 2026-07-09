"use client";

import { useState, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { THEMES, useTheme } from "@/lib/theme";

const ACCENT_GRADIENT = "linear-gradient(135deg,var(--accent),var(--accent2))";

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
  marginTop: 6,
};

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
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
      await login(email, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to search your documents."
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel="Sign in"
      error={error}
      footer={
        <>
          No account yet?{" "}
          <Link href="/register" style={linkStyle}>
            Create one
          </Link>
        </>
      }
    >
      <label style={labelStyle}>
        Email
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={inputStyle}
        />
      </label>
      <label style={{ ...labelStyle, marginTop: 14 }}>
        Password
        <input
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={inputStyle}
        />
      </label>
    </AuthShell>
  );
}

/* ---- shared shell + tokens (kept local so both auth pages match exactly) --- */
const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--muted)",
  marginBottom: 6,
};

const linkStyle: CSSProperties = {
  fontWeight: 700,
  color: "var(--accent)",
  textDecoration: "none",
};

export function AuthShell({
  title,
  subtitle,
  onSubmit,
  busy,
  submitLabel,
  error,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  onSubmit: (e: FormEvent) => void;
  busy: boolean;
  submitLabel: string;
  error: string | null;
  footer: React.ReactNode;
  children: React.ReactNode;
}) {
  const [theme, setTheme] = useTheme();
  const t = THEMES[theme];
  const isDark = theme === "dark";

  return (
    <div
      style={{
        position: "relative",
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        background: "var(--bg)",
        ...t,
      } as CSSProperties}
    >
      <button
        onClick={() => setTheme(isDark ? "light" : "dark")}
        aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
        style={{
          position: "absolute",
          top: 20,
          right: 20,
          width: 60,
          height: 30,
          borderRadius: 16,
          border: "1px solid var(--card-border)",
          background: "var(--seg-bg)",
          cursor: "pointer",
          padding: 0,
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 3,
            left: isDark ? 33 : 3,
            width: 24,
            height: 24,
            borderRadius: "50%",
            background: ACCENT_GRADIENT,
            boxShadow: "0 2px 8px var(--accentGlow)",
            transition: "left .28s cubic-bezier(.4,0,.2,1)",
          }}
        />
      </button>
      <form
        onSubmit={onSubmit}
        aria-label={title}
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
          <span
            style={{
              fontWeight: 800,
              fontSize: 20,
              letterSpacing: "-.02em",
              color: "var(--text)",
            }}
          >
            PaperTrail
          </span>
        </div>
        <h1 style={{ margin: "10px 0 4px", fontSize: 22, fontWeight: 700, color: "var(--text)" }}>
          {title}
        </h1>
        <p style={{ margin: "0 0 22px", fontSize: 14, color: "var(--muted)" }}>{subtitle}</p>

        {children}

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
          {busy ? "Please wait…" : submitLabel}
        </button>

        <p style={{ margin: "18px 0 0", fontSize: 13.5, color: "var(--muted)", textAlign: "center" }}>
          {footer}
        </p>
      </form>
    </div>
  );
}
