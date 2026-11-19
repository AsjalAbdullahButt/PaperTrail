"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/api/backendClient";
import { useAuthStore } from "@/state/authStore";
import { PasswordInput } from "@/components/ui/PasswordField";
import AuthShell from "@/components/auth/AuthShell";

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
      title="Sign in"
      subtitle="Use your PaperTrail account"
      onSubmit={handleSubmit}
      busy={busy}
      submitLabel="Sign in"
      error={error}
      footer={
        <>
          No account yet?{" "}
          <Link href="/register" className="link">
            Create one
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
        Password
        <PasswordInput
          autoComplete="current-password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(null); }}
          aria-invalid={passwordError ? true : undefined}
        />
      </label>
      {passwordError && <div className="field-error">{passwordError}</div>}
      <div style={{ textAlign: "right", marginTop: "calc(var(--space-2) * -1)" }}>
        <Link href="/forgot-password" className="link" style={{ fontSize: "var(--fs-sm)" }}>
          Forgot password?
        </Link>
      </div>
    </AuthShell>
  );
}
