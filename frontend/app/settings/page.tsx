"use client";

import {
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  ApiError,
  apiRequest,
} from "@/lib/api";
import { logout } from "@/lib/auth";

type ChangePasswordResponse = {
  status?: string;
  message?: string;
  relogin_required?: boolean;
  revoked_sessions?: number;
  revoked_refresh_tokens?: number;
};

function normalizeStatus(
  value: unknown,
): string {
  if (typeof value !== "string") {
    return "";
  }

  return value
    .trim()
    .toUpperCase();
}

function formatRole(
  value: unknown,
): string {
  const role = normalizeStatus(value);

  if (!role) {
    return "USER";
  }

  return role;
}

function formatAccountStatus(
  status: unknown,
  isActive: unknown,
  isApproved: unknown,
): string {
  const normalized =
    normalizeStatus(status);

  if (normalized) {
    return normalized;
  }

  if (isActive === false) {
    return "INACTIVE";
  }

  if (isApproved === false) {
    return "PENDING";
  }

  return "ACTIVE";
}

function getErrorMessage(
  error: unknown,
): string {
  if (
    error instanceof ApiError &&
    error.message.trim()
  ) {
    return error.message;
  }

  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return "Unable to complete this request.";
}

function SettingsContent() {
  const router = useRouter();

  const {
    user,
    isLoading,
    error,
    errorStatus,
    refreshUser,
  } = useCurrentUser();

  const [isSigningOut, setIsSigningOut] =
    useState(false);

  const signOutTimerRef =
    useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (
        signOutTimerRef.current !== null
      ) {
        window.clearTimeout(
          signOutTimerRef.current,
        );
      }
    };
  }, []);

  const [
    currentPassword,
    setCurrentPassword,
  ] = useState("");

  const [
    newPassword,
    setNewPassword,
  ] = useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [
    isChangingPassword,
    setIsChangingPassword,
  ] = useState(false);

  const [
    passwordError,
    setPasswordError,
  ] = useState<string | null>(null);

  const [
    passwordSuccess,
    setPasswordSuccess,
  ] = useState<string | null>(null);

  const displayName = useMemo(
    () =>
      user?.full_name?.trim() ||
      user?.username?.trim() ||
      user?.email?.split("@")[0] ||
      "Blue-Trading-AI User",
    [
      user?.email,
      user?.full_name,
      user?.username,
    ],
  );

  const initials = useMemo(
    () =>
      displayName
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase() || "BT",
    [displayName],
  );

  const accountRole =
    formatRole(user?.role);

  const accountStatus =
    formatAccountStatus(
      user?.account_status ??
        user?.status,
      user?.is_active,
      user?.is_approved,
    );

  async function handleSignOut() {
    if (isSigningOut) {
      return;
    }

    if (
      signOutTimerRef.current !== null
    ) {
      window.clearTimeout(
        signOutTimerRef.current,
      );
      signOutTimerRef.current = null;
    }

    try {
      setIsSigningOut(true);
      await logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  async function handlePasswordChange(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (
      isChangingPassword ||
      isSigningOut
    ) {
      return;
    }

    if (!currentPassword) {
      setPasswordError(
        "Enter your current password.",
      );
      return;
    }

    if (newPassword.length < 10) {
      setPasswordError(
        "The new password must contain at least 10 characters.",
      );
      return;
    }

    if (newPassword.length > 128) {
      setPasswordError(
        "The new password cannot exceed 128 characters.",
      );
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError(
        "The new passwords do not match.",
      );
      return;
    }

    if (currentPassword === newPassword) {
      setPasswordError(
        "The new password must be different from the current password.",
      );
      return;
    }

    try {
      setIsChangingPassword(true);
      setPasswordError(null);
      setPasswordSuccess(null);

      const result =
        await apiRequest<ChangePasswordResponse>(
          "/auth/change-password",
          {
            method: "POST",
            body: JSON.stringify({
              current_password:
                currentPassword,
              new_password:
                newPassword,
            }),
          },
        );

      setPasswordSuccess(
        result.message ||
          "Your password was changed successfully. Sign in again with the new password.",
      );

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");

      signOutTimerRef.current =
        window.setTimeout(() => {
          signOutTimerRef.current = null;
          void handleSignOut();
        }, 1800);
    } catch (requestError) {
      setPasswordError(
        getErrorMessage(requestError),
      );
    } finally {
      setIsChangingPassword(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
              Account Management
            </p>

            <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
              Settings
            </h1>

            <p className="mt-2 text-sm leading-6 text-slate-500">
              Review your account information, update your
              password and manage your secure session.
            </p>
          </div>

          {isLoading ? (
            <section className="midnight-panel rounded-3xl p-6">
              <div className="h-4 w-40 animate-pulse rounded-full bg-blue-500/10" />

              <div className="mt-5 h-24 animate-pulse rounded-2xl bg-blue-500/[0.04]" />
            </section>
          ) : null}

          {error ? (
            <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-5">
              <p className="text-sm font-black text-rose-300">
                Unable to load account information
              </p>

              <p className="mt-2 text-xs leading-5 text-slate-500">
                {error}
              </p>

              {errorStatus !== null ? (
                <p className="mt-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-700">
                  Status {errorStatus}
                </p>
              ) : null}

              <button
                type="button"
                onClick={() =>
                  void refreshUser()
                }
                className="mt-4 rounded-xl border border-blue-400/15 bg-blue-500/[0.06] px-4 py-2.5 text-xs font-black text-cyan-200"
              >
                Try Again
              </button>
            </section>
          ) : null}

          {!isLoading &&
          !error &&
          user ? (
            <>
              <section className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
                <article className="midnight-panel rounded-3xl p-6">
                  <div className="flex items-center gap-4">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-blue-400/20 bg-gradient-to-br from-blue-600/30 to-cyan-400/10 text-xl font-black text-cyan-200">
                      {initials}
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-xl font-black text-white">
                        {displayName}
                      </p>

                      <p className="mt-1 truncate text-sm text-slate-500">
                        {user.email ||
                          "Email unavailable"}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 sm:grid-cols-2">
                    {[
                      {
                        label:
                          "Account Role",
                        value:
                          accountRole,
                      },
                      {
                        label:
                          "Account Status",
                        value:
                          accountStatus,
                      },
                      {
                        label:
                          "Approved Access",
                        value:
                          user.is_approved ===
                          false
                            ? "No"
                            : "Yes",
                      },
                      {
                        label:
                          "Email Verified",
                        value:
                          user.is_email_verified ===
                          false
                            ? "No"
                            : "Yes",
                      },
                      {
                        label:
                          "Platform Access",
                        value:
                          user.can_access_platform ===
                          false
                            ? "Blocked"
                            : "Allowed",
                      },
                      {
                        label:
                          "User ID",
                        value:
                          user.id !==
                          undefined
                            ? String(
                                user.id,
                              )
                            : "Unavailable",
                      },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="midnight-card rounded-2xl p-4"
                      >
                        <p className="text-[10px] font-black uppercase tracking-[0.15em] text-slate-600">
                          {item.label}
                        </p>

                        <p className="mt-2 break-words text-sm font-black text-slate-200">
                          {item.value}
                        </p>
                      </div>
                    ))}
                  </div>
                </article>

                <article className="midnight-panel rounded-3xl p-6">
                  <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
                    Security Session
                  </p>

                  <h2 className="mt-2 text-xl font-black text-white">
                    Signed-in session
                  </h2>

                  <p className="mt-3 text-sm leading-6 text-slate-500">
                    Your session is protected by backend token
                    validation and automatic refresh rotation.
                  </p>

                  <div className="mt-5 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] p-4">
                    <div className="flex items-center gap-2">
                      <span className="midnight-status-dot h-2 w-2 rounded-full bg-emerald-400" />

                      <p className="text-xs font-black text-emerald-300">
                        Session active
                      </p>
                    </div>

                    <p className="mt-2 text-xs leading-5 text-slate-600">
                      Current role: {accountRole}
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={
                      isSigningOut ||
                      isChangingPassword
                    }
                    onClick={() =>
                      void handleSignOut()
                    }
                    className="mt-6 w-full rounded-xl border border-rose-400/20 bg-rose-400/[0.06] py-3.5 text-sm font-black text-rose-300 transition hover:bg-rose-400/[0.1] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isSigningOut
                      ? "Signing out..."
                      : "Sign Out"}
                  </button>
                </article>
              </section>

              <section className="midnight-panel rounded-3xl p-6">
                <div className="max-w-2xl">
                  <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
                    Password Security
                  </p>

                  <h2 className="mt-2 text-xl font-black text-white">
                    Change your password
                  </h2>

                  <p className="mt-3 text-sm leading-6 text-slate-500">
                    Use at least 10 characters. Changing your
                    password revokes existing sessions and
                    requires a fresh login.
                  </p>
                </div>

                <form
                  onSubmit={
                    handlePasswordChange
                  }
                  className="mt-6 grid gap-5 lg:max-w-2xl"
                >
                  <div>
                    <label
                      htmlFor="currentPassword"
                      className="text-xs font-black text-slate-300"
                    >
                      Current password
                    </label>

                    <input
                      id="currentPassword"
                      type="password"
                      autoComplete="current-password"
                      required
                      maxLength={128}
                      value={currentPassword}
                      onChange={(event) => {
                        setCurrentPassword(
                          event.target.value,
                        );
                        setPasswordError(null);
                        setPasswordSuccess(null);
                      }}
                      placeholder="Enter your current password"
                      className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06]"
                    />
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="newPassword"
                        className="text-xs font-black text-slate-300"
                      >
                        New password
                      </label>

                      <input
                        id="newPassword"
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={10}
                        maxLength={128}
                        value={newPassword}
                        onChange={(event) => {
                          setNewPassword(
                            event.target.value,
                          );
                          setPasswordError(null);
                          setPasswordSuccess(null);
                        }}
                        placeholder="Minimum 10 characters"
                        className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06]"
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="confirmPassword"
                        className="text-xs font-black text-slate-300"
                      >
                        Confirm password
                      </label>

                      <input
                        id="confirmPassword"
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={10}
                        maxLength={128}
                        value={confirmPassword}
                        onChange={(event) => {
                          setConfirmPassword(
                            event.target.value,
                          );
                          setPasswordError(null);
                          setPasswordSuccess(null);
                        }}
                        placeholder="Repeat the new password"
                        className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06]"
                      />
                    </div>
                  </div>

                  {passwordError ? (
                    <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3">
                      <p className="text-xs font-bold leading-5 text-rose-300">
                        {passwordError}
                      </p>
                    </div>
                  ) : null}

                  {passwordSuccess ? (
                    <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-4 py-3">
                      <p className="text-xs font-bold leading-5 text-emerald-300">
                        {passwordSuccess}
                      </p>

                      <p className="mt-2 text-[10px] text-slate-600">
                        Returning to login...
                      </p>
                    </div>
                  ) : null}

                  <button
                    type="submit"
                    disabled={
                      isChangingPassword ||
                      isSigningOut
                    }
                    className="midnight-button rounded-xl px-6 py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60 sm:w-fit"
                  >
                    {isChangingPassword
                      ? "Changing password..."
                      : "Change Password"}
                  </button>
                </form>
              </section>
            </>
          ) : null}
    </div>
  );
}

export default function SettingsPage() {
  return <SettingsContent />;
}