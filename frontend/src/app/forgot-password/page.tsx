"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, forgotPassword } from "@/lib/api";
import { AuthShell, fieldErrorStyle, inputStyle, labelStyle, linkStyle } from "../login/page";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;

    setError(null);
    if (!email.trim()) {
      setEmailError("Email is required.");
      return;
    }
    setEmailError(null);

    setBusy(true);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your account email and we'll send a reset link."
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel={sent ? "Send again" : "Send reset link"}
      error={error}
      footer={
        <>
          Remembered it?{" "}
          <Link href="/login" style={linkStyle}>
            Sign in
          </Link>
        </>
      }
    >
      {sent && (
        <div
          role="status"
          style={{
            marginBottom: 16,
            padding: "10px 14px",
            borderRadius: 12,
            fontSize: 13.5,
            color: "var(--accent)",
            background: "var(--chip-bg)",
            border: "1px solid var(--chip-border)",
          }}
        >
          If that email is registered, a reset link is on its way.
        </div>
      )}
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
    </AuthShell>
  );
}
