"use client";

import { Suspense, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ApiError, resetPassword } from "@/lib/api";
import { AuthShell, fieldErrorStyle, inputStyle, labelStyle, linkStyle } from "../login/page";
import { PasswordInput, PasswordStrengthMeter, passwordComplexityError } from "@/components/PasswordField";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;

    setError(null);
    if (!token) {
      setError("This reset link is missing its token. Request a new one.");
      return;
    }

    let ok = true;
    const pwError = passwordComplexityError(password);
    if (pwError) {
      setPasswordError(pwError);
      ok = false;
    } else {
      setPasswordError(null);
    }
    if (!pwError && password !== confirm) {
      setConfirmError("Passwords do not match.");
      ok = false;
    } else {
      setConfirmError(null);
    }
    if (!ok) return;

    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Set a new password"
      subtitle="Choose a new password for your account."
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel={done ? "Redirecting…" : "Reset password"}
      error={error}
      footer={
        <>
          Back to{" "}
          <Link href="/login" style={linkStyle}>
            Sign in
          </Link>
        </>
      }
    >
      {done ? (
        <div
          role="status"
          style={{
            padding: "10px 14px",
            borderRadius: 12,
            fontSize: 13.5,
            color: "var(--accent)",
            background: "var(--chip-bg)",
            border: "1px solid var(--chip-border)",
          }}
        >
          Password reset. Redirecting you to sign in…
        </div>
      ) : (
        <>
          <label style={labelStyle}>
            New password
            <PasswordInput
              autoComplete="new-password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(null); }}
              style={inputStyle}
              aria-invalid={passwordError ? true : undefined}
            />
          </label>
          {passwordError && <div style={fieldErrorStyle}>{passwordError}</div>}
          <PasswordStrengthMeter password={password} />
          <label style={{ ...labelStyle, marginTop: 14 }}>
            Confirm new password
            <PasswordInput
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); if (confirmError) setConfirmError(null); }}
              style={inputStyle}
              aria-invalid={confirmError ? true : undefined}
            />
          </label>
          {confirmError && <div style={fieldErrorStyle}>{confirmError}</div>}
        </>
      )}
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
