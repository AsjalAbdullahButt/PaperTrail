"use client";

import { useState, type CSSProperties, type InputHTMLAttributes } from "react";

/** Same rule the backend enforces (schemas.py's _check_password_complexity):
 *  at least 8 characters, at least one letter, at least one number. Mirrored
 *  here (not reinvented) so the client-side checklist never drifts from what
 *  the server will actually accept. */
export function passwordRules(password: string): { label: string; met: boolean }[] {
  return [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "Contains a letter", met: /[a-zA-Z]/.test(password) },
    { label: "Contains a number", met: /[0-9]/.test(password) },
  ];
}

/** First unmet server-side rule as a user-facing message, or null if the
 * password satisfies every rule the backend checks. */
export function passwordComplexityError(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
    return "Password must contain at least one letter and one number.";
  }
  return null;
}

type Strength = "weak" | "medium" | "strong";

/** Weak/medium/strong is a UX-only refinement on top of the pass/fail rules
 * above (length bonus for "strong") — it never implies a requirement the
 * server doesn't also enforce. */
function strengthOf(password: string): Strength {
  const metCount = passwordRules(password).filter((r) => r.met).length;
  if (metCount < 3) return "weak";
  return password.length >= 12 ? "strong" : "medium";
}

const STRENGTH_META: Record<Strength, { label: string; color: string; pct: string }> = {
  weak: { label: "Weak", color: "#ff8a80", pct: "33%" },
  medium: { label: "Medium", color: "#e0a53a", pct: "66%" },
  strong: { label: "Strong", color: "var(--accent)", pct: "100%" },
};

/** Live strength label + rule checklist, updating on keystroke. Renders
 * nothing until the user has typed something. */
export function PasswordStrengthMeter({ password }: { password: string }) {
  if (!password) return null;
  const rules = passwordRules(password);
  const strength = strengthOf(password);
  const meta = STRENGTH_META[strength];

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1, height: 4, borderRadius: 2, background: "var(--seg-bg)", overflow: "hidden" }}>
          <div
            style={{
              width: meta.pct,
              height: "100%",
              background: meta.color,
              transition: "width .2s ease, background .2s ease",
            }}
          />
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: meta.color, whiteSpace: "nowrap" }}>
          {meta.label}
        </span>
      </div>
      <ul style={{ listStyle: "none", margin: "8px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 3 }}>
        {rules.map((r) => (
          <li key={r.label} style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: r.met ? "var(--accent)" : "#ff8a80", fontWeight: 700 }} aria-hidden>
              {r.met ? "✓" : "✗"}
            </span>
            {r.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.9 4.24A9.8 9.8 0 0 1 12 4c7 0 11 7 11 7a17.6 17.6 0 0 1-3.06 3.94M6.6 6.6C3.5 8.6 1 12 1 12s4 7 11 7a9.7 9.7 0 0 0 4.6-1.13M9.9 9.9a3 3 0 0 0 4.24 4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

const wrapStyle: CSSProperties = { position: "relative" };
const toggleStyle: CSSProperties = {
  position: "absolute",
  right: 6,
  top: "50%",
  transform: "translateY(-50%)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 32,
  height: 32,
  padding: 0,
  border: "none",
  background: "none",
  color: "var(--muted)",
  cursor: "pointer",
};

/** Password input with an eye toggle inside a relative wrapper. Forwards every
 * other prop straight to the underlying <input>. */
export function PasswordInput({
  style,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div style={wrapStyle}>
      <input {...props} type={visible ? "text" : "password"} style={{ ...style, paddingRight: 40 }} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        style={toggleStyle}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}
