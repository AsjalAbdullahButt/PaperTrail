"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import AuthenticatedPageLayout from "@/components/layout/AuthenticatedPageLayout";
import {
  ApiError,
  changePassword,
  deleteAccount,
  deleteAvatar,
  resolveApiUrl,
  updateProfile,
  uploadAvatar,
} from "@/api/backendClient";
import { useAuthStore } from "@/state/authStore";
import {
  PasswordInput,
  PasswordStrengthMeter,
  passwordComplexityError,
} from "@/components/ui/PasswordField";

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
    <form onSubmit={handleSubmit} noValidate className="card" aria-labelledby="profile-title">
      <h2 id="profile-title" className="h-section" style={{ marginBottom: "var(--space-4)" }}>Profile</h2>

      <div className="row" style={{ gap: "var(--space-4)", marginBottom: "var(--space-5)", flexWrap: "wrap" }}>
        <div
          aria-hidden
          style={{
            width: 64, height: 64, borderRadius: "50%", overflow: "hidden", flex: "none",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: "var(--accent)",
            color: "var(--on-accent)", fontSize: "var(--fs-xl)", fontWeight: "var(--fw-semibold)",
          }}
        >
          {avatarSrc ? (
            // eslint-disable-next-line @next/next/no-img-element -- external/backend-served, not a static asset
            <img src={avatarSrc} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            initials
          )}
        </div>
        <div className="stack" style={{ gap: "var(--space-2)" }}>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <button type="button" className="btn btn-sm" onClick={() => fileRef.current?.click()} disabled={avatarBusy}>
              {avatarBusy ? "Uploading…" : "Upload avatar"}
            </button>
            {avatarSrc && (
              <button type="button" className="btn btn-sm btn-ghost" onClick={handleAvatarRemove} disabled={avatarBusy}>
                Remove
              </button>
            )}
          </div>
          <span className="meta">JPEG, PNG, WebP, or GIF — up to 2 MB.</span>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleAvatarChange}
          aria-label="Avatar image"
          style={{ display: "none" }}
        />
      </div>

      <div className="stack">
        <label className="field">
          Display name
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
          Bio
          <textarea
            maxLength={2000}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            className="input"
          />
        </label>
      </div>
      {error && <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-4)" }}>{error}</div>}
      <button type="submit" disabled={busy} className="btn btn-primary" style={{ marginTop: "var(--space-5)" }}>
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
    <form onSubmit={handleSubmit} noValidate className="card" aria-labelledby="password-title" style={{ marginTop: "var(--space-4)" }}>
      <h2 id="password-title" className="h-section" style={{ marginBottom: "var(--space-4)" }}>Change password</h2>
      <div className="stack">
        <label className="field">
          Current password
          <PasswordInput
            autoComplete="current-password"
            value={current}
            onChange={(e) => { setCurrent(e.target.value); if (currentError) setCurrentError(null); }}
            aria-invalid={currentError ? true : undefined}
          />
        </label>
        {currentError && <div className="field-error">{currentError}</div>}
        <label className="field">
          New password
          <PasswordInput
            autoComplete="new-password"
            value={next}
            onChange={(e) => { setNext(e.target.value); if (nextError) setNextError(null); }}
            aria-invalid={nextError ? true : undefined}
          />
        </label>
        {nextError && <div className="field-error">{nextError}</div>}
        <PasswordStrengthMeter password={next} />
        <label className="field">
          Confirm new password
          <PasswordInput
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => { setConfirm(e.target.value); if (confirmError) setConfirmError(null); }}
            aria-invalid={confirmError ? true : undefined}
          />
        </label>
        {confirmError && <div className="field-error">{confirmError}</div>}
      </div>
      {error && <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-4)" }}>{error}</div>}
      <button type="submit" disabled={busy} className="btn btn-primary" style={{ marginTop: "var(--space-5)" }}>
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
    <section className="card" aria-labelledby="danger-title" style={{ marginTop: "var(--space-4)", borderColor: "var(--danger-line)" }}>
      <h2 id="danger-title" className="h-section" style={{ color: "var(--danger)", marginBottom: "var(--space-2)" }}>Danger zone</h2>
      <p style={{ marginBottom: "var(--space-4)", fontSize: "var(--fs-sm)", color: "var(--text-2)" }}>
        Deleting your account permanently removes your profile, documents, and query history. This cannot be undone.
      </p>
      {!confirming ? (
        <button type="button" onClick={() => setConfirming(true)} className="btn btn-danger">
          Delete account
        </button>
      ) : (
        <div>
          <label className="field">
            Type DELETE to confirm
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="input"
              autoComplete="off"
            />
          </label>
          {error && <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-3)" }}>{error}</div>}
          <div className="row" style={{ marginTop: "var(--space-4)" }}>
            <button
              type="button"
              className="btn btn-danger"
              onClick={handleDelete}
              disabled={confirmText.trim().toUpperCase() !== "DELETE" || busy}
            >
              {busy ? "Deleting…" : "Permanently delete"}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => { setConfirming(false); setConfirmText(""); setError(null); }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ProfilePageContent() {
  const user = useAuthStore((s) => s.user);

  return (
    <div style={{ maxWidth: 640 }}>
      <h1 className="h-page" style={{ marginBottom: "var(--space-5)" }}>
        Account settings
      </h1>
      {user && (
        // Keyed on user.id so the forms re-key (and re-derive their initial
        // field state) once the user record actually loads, instead of
        // staying stuck pre-filled with empty strings from before
        // restoreSession resolved.
        <>
          <ProfileForm key={user.id} />
          <ChangePasswordForm />
          <DeleteAccountSection />
        </>
      )}
    </div>
  );
}

export default function ProfilePage() {
  return (
    <AuthenticatedPageLayout>
      <ProfilePageContent />
    </AuthenticatedPageLayout>
  );
}
