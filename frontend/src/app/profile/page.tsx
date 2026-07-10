"use client";

import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import PageShell from "@/components/PageShell";
import {
  ApiError,
  changePassword,
  deleteAccount,
  deleteAvatar,
  resolveApiUrl,
  updateProfile,
  uploadAvatar,
} from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import {
  PasswordInput,
  PasswordStrengthMeter,
  passwordComplexityError,
} from "@/components/PasswordField";

const cardStyle: CSSProperties = {
  padding: "22px 24px",
  borderRadius: 20,
  background: "var(--card-bg)",
  border: "1px solid var(--card-border)",
  backdropFilter: "blur(18px) saturate(140%)",
  boxShadow: "0 12px 34px var(--cardShadow)",
};

const labelStyle: CSSProperties = {
  display: "block",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--muted)",
  marginBottom: 6,
};

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

const textareaStyle: CSSProperties = { ...inputStyle, resize: "vertical", minHeight: 84 };

const fieldErrorStyle: CSSProperties = { marginTop: 6, fontSize: 12.5, color: "#ff8a80" };

const sectionTitleStyle: CSSProperties = {
  fontSize: 11.5,
  fontWeight: 700,
  letterSpacing: ".05em",
  textTransform: "uppercase",
  color: "var(--muted)",
  marginBottom: 14,
};

const buttonStyle: CSSProperties = {
  padding: "11px 20px",
  borderRadius: 12,
  border: "none",
  cursor: "pointer",
  fontFamily: "inherit",
  fontWeight: 700,
  fontSize: 14,
  color: "var(--onAccent)",
  background: "linear-gradient(135deg,var(--accent),var(--accent2))",
  boxShadow: "0 4px 14px var(--accentGlow)",
};

const dangerButtonStyle: CSSProperties = {
  ...buttonStyle,
  color: "#ff8a80",
  background: "rgba(255,80,80,.10)",
  border: "1px solid rgba(255,120,120,.35)",
  boxShadow: "none",
};

function bannerStyle(kind: "error" | "ok"): CSSProperties {
  return {
    marginTop: 14,
    padding: "10px 14px",
    borderRadius: 12,
    fontSize: 13.5,
    color: kind === "error" ? "#ff8a80" : "var(--accent)",
    background: kind === "error" ? "rgba(255,80,80,.10)" : "var(--chip-bg)",
    border: `1px solid ${kind === "error" ? "rgba(255,120,120,.35)" : "var(--chip-border)"}`,
  };
}

const AVATAR_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const AVATAR_MAX_BYTES = 2 * 1024 * 1024;

function ProfileForm() {
  const user = useAuthStore((s) => s.user);
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [busy, setBusy] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateProfile({
        display_name: displayName.trim() || null,
        bio: bio.trim() || null,
        avatar_url: user?.avatar_url ?? null, // avatar is managed separately, below
      });
      useAuthStore.setState({ user: updated });
      toast.success("Profile saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAvatarChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    if (!AVATAR_TYPES.has(file.type)) {
      toast.error("Avatar must be a JPEG, PNG, WebP, or GIF image.");
      return;
    }
    if (file.size > AVATAR_MAX_BYTES) {
      toast.error("Avatar image must be under 2 MB.");
      return;
    }
    setAvatarBusy(true);
    try {
      const updated = await uploadAvatar(file);
      useAuthStore.setState({ user: updated });
      toast.success("Avatar updated.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Avatar upload failed.");
    } finally {
      setAvatarBusy(false);
    }
  }

  async function handleAvatarRemove() {
    setAvatarBusy(true);
    try {
      const updated = await deleteAvatar();
      useAuthStore.setState({ user: updated });
      toast.success("Avatar removed.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove avatar.");
    } finally {
      setAvatarBusy(false);
    }
  }

  const avatarSrc = user?.avatar_url ? resolveApiUrl(user.avatar_url) : null;
  const initials = (user?.display_name || user?.email || "?").trim().charAt(0).toUpperCase();

  return (
    <form onSubmit={handleSubmit} noValidate style={cardStyle}>
      <div style={sectionTitleStyle}>Profile</div>

      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <div
          style={{
            width: 64, height: 64, borderRadius: "50%", overflow: "hidden", flex: "none",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: "linear-gradient(135deg,var(--accent),var(--accent2))",
            color: "var(--onAccent)", fontSize: 24, fontWeight: 800,
          }}
        >
          {avatarSrc ? (
            // eslint-disable-next-line @next/next/no-img-element -- external/backend-served, not a static asset
            <img src={avatarSrc} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            initials
          )}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={avatarBusy}
              style={{ ...buttonStyle, padding: "8px 14px", fontSize: 13, opacity: avatarBusy ? 0.75 : 1 }}
            >
              {avatarBusy ? "Uploading…" : "Upload avatar"}
            </button>
            {avatarSrc && (
              <button
                type="button"
                onClick={handleAvatarRemove}
                disabled={avatarBusy}
                style={{
                  padding: "8px 14px", borderRadius: 12, border: "1px solid var(--card-border)",
                  background: "var(--seg-bg)", color: "var(--text)", fontFamily: "inherit",
                  fontWeight: 700, fontSize: 13, cursor: "pointer", opacity: avatarBusy ? 0.75 : 1,
                }}
              >
                Remove
              </button>
            )}
          </div>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>JPEG, PNG, WebP, or GIF — up to 2 MB.</span>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleAvatarChange}
          style={{ display: "none" }}
        />
      </div>

      <label style={labelStyle}>
        Display name
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
        Bio
        <textarea
          maxLength={2000}
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          style={textareaStyle}
        />
      </label>
      {error && <div style={bannerStyle("error")} role="alert">{error}</div>}
      <button type="submit" disabled={busy} style={{ ...buttonStyle, marginTop: 16, opacity: busy ? 0.75 : 1 }}>
        {busy ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}

function ChangePasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [currentError, setCurrentError] = useState<string | null>(null);
  const [nextError, setNextError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);

    let ok = true;
    if (!current) {
      setCurrentError("Current password is required.");
      ok = false;
    } else {
      setCurrentError(null);
    }
    const pwError = passwordComplexityError(next);
    if (pwError) {
      setNextError(pwError);
      ok = false;
    } else {
      setNextError(null);
    }
    if (!pwError && next !== confirm) {
      setConfirmError("Passwords do not match.");
      ok = false;
    } else {
      setConfirmError(null);
    }
    if (!ok) return;

    setBusy(true);
    try {
      await changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password changed. Other sessions were signed out.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate style={{ ...cardStyle, marginTop: 20 }}>
      <div style={sectionTitleStyle}>Change password</div>
      <label style={labelStyle}>
        Current password
        <PasswordInput
          autoComplete="current-password"
          value={current}
          onChange={(e) => { setCurrent(e.target.value); if (currentError) setCurrentError(null); }}
          style={inputStyle}
          aria-invalid={currentError ? true : undefined}
        />
      </label>
      {currentError && <div style={fieldErrorStyle}>{currentError}</div>}
      <label style={{ ...labelStyle, marginTop: 14 }}>
        New password
        <PasswordInput
          autoComplete="new-password"
          value={next}
          onChange={(e) => { setNext(e.target.value); if (nextError) setNextError(null); }}
          style={inputStyle}
          aria-invalid={nextError ? true : undefined}
        />
      </label>
      {nextError && <div style={fieldErrorStyle}>{nextError}</div>}
      <PasswordStrengthMeter password={next} />
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
      {error && <div style={bannerStyle("error")} role="alert">{error}</div>}
      <button type="submit" disabled={busy} style={{ ...buttonStyle, marginTop: 16, opacity: busy ? 0.75 : 1 }}>
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}

function DeleteAccountSection() {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (confirmText.trim().toUpperCase() !== "DELETE" || busy) return;
    setBusy(true);
    setError(null);
    try {
      await deleteAccount();
      useAuthStore.setState({ user: null, accessToken: null, isAuthenticated: false, ready: true });
      toast.success("Account deleted.");
      router.replace("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <div style={{ ...cardStyle, marginTop: 20, borderColor: "rgba(255,120,120,.25)" }}>
      <div style={{ ...sectionTitleStyle, color: "#ff8a80" }}>Danger zone</div>
      <p style={{ margin: "0 0 14px", fontSize: 13.5, color: "var(--muted)" }}>
        Deleting your account permanently removes your profile, documents, and query history. This cannot be undone.
      </p>
      {!confirming ? (
        <button type="button" onClick={() => setConfirming(true)} style={dangerButtonStyle}>
          Delete account
        </button>
      ) : (
        <div>
          <label style={labelStyle}>
            Type DELETE to confirm
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              style={inputStyle}
              autoComplete="off"
            />
          </label>
          {error && <div style={bannerStyle("error")} role="alert">{error}</div>}
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button
              type="button"
              onClick={handleDelete}
              disabled={confirmText.trim().toUpperCase() !== "DELETE" || busy}
              style={{
                ...dangerButtonStyle,
                opacity: confirmText.trim().toUpperCase() === "DELETE" && !busy ? 1 : 0.5,
                cursor: confirmText.trim().toUpperCase() === "DELETE" && !busy ? "pointer" : "default",
              }}
            >
              {busy ? "Deleting…" : "Permanently delete"}
            </button>
            <button
              type="button"
              onClick={() => { setConfirming(false); setConfirmText(""); setError(null); }}
              style={{ ...buttonStyle, background: "var(--seg-bg)", color: "var(--text)", boxShadow: "none", border: "1px solid var(--card-border)" }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfilePageContent() {
  const user = useAuthStore((s) => s.user);
  // Re-key the forms once the user record actually loads, so the display-name
  // field isn't stuck pre-filled with an empty string from before restoreSession
  // resolved.
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (user) setReady(true);
  }, [user]);

  return (
    <div style={{ maxWidth: 560, margin: "0 auto" }}>
      <h1 style={{ margin: "0 0 20px", fontSize: 24, fontWeight: 700, color: "var(--text)" }}>
        Account settings
      </h1>
      {ready && (
        <>
          <ProfileForm key={user?.id} />
          <ChangePasswordForm />
          <DeleteAccountSection />
        </>
      )}
    </div>
  );
}

export default function ProfilePage() {
  return (
    <PageShell>
      <ProfilePageContent />
    </PageShell>
  );
}
