"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { AuthShell, fieldErrorStyle, inputStyle, labelStyle, linkStyle } from "../login/page";
import { PasswordInput, PasswordStrengthMeter, passwordComplexityError } from "@/components/PasswordField";

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
      subtitle="Register to start uploading and querying documents."
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel="Create account"
      error={error}
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" style={linkStyle}>
            Sign in
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
        Display name <span style={{ fontWeight: 400 }}>(optional)</span>
        <input
          type="text"
          maxLength={100}
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          style={inputStyle}
        />
      </label>
      <label style={{ ...labelStyle, marginTop: 14 }}>
        Password
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
        Confirm password
        <PasswordInput
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => { setConfirm(e.target.value); if (confirmError) setConfirmError(null); }}
          style={inputStyle}
          aria-invalid={confirmError ? true : undefined}
        />
      </label>
      {confirmError && <div style={fieldErrorStyle}>{confirmError}</div>}
    </AuthShell>
  );
}
