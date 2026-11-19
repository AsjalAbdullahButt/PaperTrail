"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/api/backendClient";
import { useAuthStore } from "@/state/authStore";
import AuthShell from "@/components/auth/AuthShell";
import { PasswordInput, PasswordStrengthMeter, passwordComplexityError } from "@/components/ui/PasswordField";

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

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
      await register(email, password, displayName.trim() || undefined);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Upload documents and ask questions about them"
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel="Create account"
      error={error}
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="link">
            Sign in
          </Link>
        </>
      }
    >
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
      <label className="field">
        Display name <span style={{ fontWeight: "var(--fw-regular)", color: "var(--muted)" }}>(optional)</span>
        <input
          type="text"
          maxLength={100}
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="input"
        />
      </label>
      <label className="field">
        Password
        <PasswordInput
          autoComplete="new-password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(null); }}
          aria-invalid={passwordError ? true : undefined}
        />
      </label>
      {passwordError && <div className="field-error">{passwordError}</div>}
      <PasswordStrengthMeter password={password} />
      <label className="field">
        Confirm password
        <PasswordInput
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => { setConfirm(e.target.value); if (confirmError) setConfirmError(null); }}
          aria-invalid={confirmError ? true : undefined}
        />
      </label>
      {confirmError && <div className="field-error">{confirmError}</div>}
    </AuthShell>
  );
}
