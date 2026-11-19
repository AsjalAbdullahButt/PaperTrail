"use client";

import { useState, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/api/backendClient";
import { useAuthStore } from "@/state/authStore";
import { THEMES, useTheme } from "@/theme/themes";
import { PasswordInput } from "@/components/ui/PasswordField";
import PaperTrailLogo from "@/components/layout/PaperTrailLogo";


export const inputStyle: CSSProperties = {
  width: "100%",
  padding: "12px 14px",
  borderRadius: "var(--radius-md)",
  background: "var(--raised)",
  border: "1px solid var(--border)",
  color: "var(--text)",
  fontFamily: "inherit",
  fontSize: "var(--fs-md)",
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
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;

    setError(null);
    let ok = true;
    if (!email.trim()) {
      setEmailError("Email is required.");
      ok = false;
    } else {
      setEmailError(null);
    }
    if (!password) {
      setPasswordError("Password is required.");
      ok = false;
    } else {
      setPasswordError(null);
    }
    if (!ok) return;

    setBusy(true);
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
          autoComplete="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (emailError) setEmailError(null); }}
          style={inputStyle}
          aria-invalid={emailError ? true : undefined}
        />
      </label>
      {emailError && <div style={fieldErrorStyle}>{emailError}</div>}
      <label style={{ ...labelStyle, marginTop: 14 }}>
        Password
        <PasswordInput
          autoComplete="current-password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(null); }}
          style={inputStyle}
          aria-invalid={passwordError ? true : undefined}
        />
      </label>
      {passwordError && <div style={fieldErrorStyle}>{passwordError}</div>}
      <div style={{ marginTop: 10, textAlign: "right" }}>
        <Link href="/forgot-password" style={{ ...linkStyle, fontSize: "var(--fs-sm)" }}>
          Forgot password?
        </Link>
      </div>
    </AuthShell>
  );
}

/* ---- shared shell + tokens, reused by every auth-styled page --- */
export const labelStyle: CSSProperties = {
  display: "block",
  fontSize: "var(--fs-sm)",
  fontWeight: "var(--fw-medium)",
  color: "var(--muted)",
  marginBottom: 6,
};

export const linkStyle: CSSProperties = {
  fontWeight: "var(--fw-semibold)",
  color: "var(--accent)",
  textDecoration: "none",
};

export const fieldErrorStyle: CSSProperties = {
  marginTop: 6,
  fontSize: "var(--fs-xs)",
  color: "var(--danger)",
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
          borderRadius: "var(--radius-md)",
          border: "1px solid var(--border)",
          background: "var(--raised)",
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
            background: "var(--accent)",
            transition: "left .28s cubic-bezier(.4,0,.2,1)",
          }}
        />
      </button>
      <form
        onSubmit={onSubmit}
        noValidate
        aria-label={title}
        style={{
          width: "100%",
          maxWidth: 400,
          padding: "clamp(24px, 6vw, 34px) clamp(20px, 5vw, 32px)",
          borderRadius: "var(--radius-md)",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-overlay)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 6 }}>
          <PaperTrailLogo />
          <span
            style={{
              fontWeight: "var(--fw-semibold)",
              fontSize: "var(--fs-lg)",
              letterSpacing: "-.02em",
              color: "var(--text)",
            }}
          >
            PaperTrail
          </span>
        </div>
        <h1 style={{ margin: "10px 0 4px", fontSize: "var(--fs-lg)", fontWeight: "var(--fw-semibold)", color: "var(--text)" }}>
          {title}
        </h1>
        <p style={{ margin: "0 0 22px", fontSize: "var(--fs-sm)", color: "var(--muted)" }}>{subtitle}</p>

        {children}

        {error && (
          <div
            role="alert"
            style={{
              marginTop: 16,
              padding: "10px 14px",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--fs-sm)",
              color: "var(--danger)",
              background: "var(--danger-soft)",
              border: "1px solid var(--danger-line)",
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
            borderRadius: "var(--radius-md)",
            border: "none",
            cursor: busy ? "default" : "pointer",
            fontFamily: "inherit",
            fontWeight: "var(--fw-semibold)",
            fontSize: "var(--fs-md)",
            color: "var(--on-accent)",
            background: "var(--accent)",
            opacity: busy ? 0.75 : 1,
          }}
        >
          {busy ? "Please wait…" : submitLabel}
        </button>

        <p style={{ margin: "18px 0 0", fontSize: "var(--fs-sm)", color: "var(--muted)", textAlign: "center" }}>
          {footer}
        </p>
      </form>
    </div>
  );
}
