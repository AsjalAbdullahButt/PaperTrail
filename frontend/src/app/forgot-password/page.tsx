"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { ApiError, forgotPassword } from "@/api/backendClient";
import AuthShell from "@/components/auth/AuthShell";

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
      subtitle="Enter your account email and we'll send a reset link"
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel={sent ? "Send again" : "Send reset link"}
      error={error}
      footer={
        <>
          Remembered it?{" "}
          <Link href="/login" className="link">
            Sign in
          </Link>
        </>
      }
    >
      {sent && (
        <div role="status" className="alert alert-ok">
          If that email is registered, a reset link is on its way.
        </div>
      )}
      <label className="field">
        Email
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (emailError) setEmailError(null); }}
          className="input"
          aria-invalid={emailError ? true : undefined}
        />
      </label>
      {emailError && <div className="field-error">{emailError}</div>}
    </AuthShell>
  );
}
