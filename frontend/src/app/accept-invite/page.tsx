"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Shield,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  CheckCircle,
  XCircle,
  User,
} from "lucide-react";
import api from "@/lib/api";

type AcceptState = "form" | "submitting" | "success" | "error";

export default function AcceptInvitePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      }
    >
      <AcceptInviteContent />
    </Suspense>
  );
}

function AcceptInviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [acceptState, setAcceptState] = useState<AcceptState>("form");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // If no token in URL, show error immediately
  useEffect(() => {
    if (!token) {
      setAcceptState("error");
      setErrorMessage(
        "No invitation token found. Please check the link you received.",
      );
    }
  }, [token]);

  const validatePassword = (pw: string): string[] => {
    const errors: string[] = [];
    if (pw.length < 8) errors.push("At least 8 characters");
    if (!/[a-z]/.test(pw)) errors.push("A lowercase letter");
    if (!/[A-Z]/.test(pw)) errors.push("An uppercase letter");
    if (!/\d/.test(pw)) errors.push("A digit");
    if (!/[^a-zA-Z0-9]/.test(pw)) errors.push("A special character");
    return errors;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Client-side validation
    const pwErrors = validatePassword(password);
    if (pwErrors.length > 0) {
      setValidationErrors(pwErrors);
      return;
    }
    setValidationErrors([]);

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    if (!fullName.trim()) {
      setErrorMessage("Full name is required.");
      return;
    }

    setAcceptState("submitting");

    try {
      await api.post("/invitations/accept", {
        token,
        password,
        full_name: fullName.trim(),
      });
      setAcceptState("success");
    } catch (err: unknown) {
      setAcceptState("error");
      const axiosErr = err as {
        response?: { data?: { detail?: string }; status?: number };
      };
      const detail = axiosErr.response?.data?.detail;
      if (axiosErr.response?.status === 410) {
        setErrorMessage(
          "This invitation has expired. Please ask your administrator to send a new one.",
        );
      } else if (axiosErr.response?.status === 422) {
        setErrorMessage(detail ?? "Password does not meet requirements.");
      } else {
        setErrorMessage(
          detail ?? "Invalid or expired invitation. Please request a new one.",
        );
      }
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      {/* Background effects (same as login page) */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(99,102,241,0.12) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,27,75,0.9) 50%, rgba(15,23,42,0.95) 100%)",
        }}
      />
      <div
        className="pointer-events-none absolute -left-32 -top-32 z-0 h-[500px] w-[500px] rounded-full opacity-20 blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, rgba(99,102,241,0.6) 0%, transparent 70%)",
        }}
      />
      <div
        className="pointer-events-none absolute -bottom-32 -right-32 z-0 h-[400px] w-[400px] rounded-full opacity-15 blur-[100px]"
        style={{
          background:
            "radial-gradient(circle, rgba(59,130,246,0.5) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
            <Shield size={20} className="text-indigo-400" />
          </div>
          <span className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
            CSPM Platform
          </span>
        </div>

        {/* Glass card */}
        <div
          className="rounded-2xl border border-white/[0.08] p-8 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-10"
          style={{
            background:
              "linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
          }}
        >
          {/* -- Success State -- */}
          {acceptState === "success" && (
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/10">
                <CheckCircle size={32} className="text-green-400" />
              </div>
              <h2 className="text-xl font-semibold text-white">
                Account Created
              </h2>
              <p className="mt-3 text-sm text-slate-400">
                Your account has been set up successfully. You can now sign in
                with your credentials.
              </p>
              <button
                onClick={() => router.push("/login")}
                className="group mt-6 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all duration-300"
                style={{
                  background:
                    "linear-gradient(135deg, rgb(99,102,241) 0%, rgb(59,130,246) 100%)",
                  boxShadow:
                    "0 0 20px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.3)",
                }}
              >
                <span>Go to Login</span>
                <ArrowRight
                  size={16}
                  className="transition-transform duration-300 group-hover:translate-x-0.5"
                />
              </button>
            </div>
          )}

          {/* -- Error State (no token or invalid) -- */}
          {acceptState === "error" && (
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
                <XCircle size={32} className="text-red-400" />
              </div>
              <h2 className="text-xl font-semibold text-white">
                Invitation Error
              </h2>
              <p className="mt-3 text-sm text-slate-400">
                {errorMessage ??
                  "This invitation link is invalid or has expired."}
              </p>
              <button
                onClick={() => {
                  if (token) {
                    setAcceptState("form");
                    setErrorMessage(null);
                  } else {
                    router.push("/login");
                  }
                }}
                className="group mt-6 flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] px-4 py-3 text-sm font-medium text-slate-300 transition-all duration-300 hover:bg-white/[0.04]"
              >
                {token ? "Try Again" : "Go to Login"}
              </button>
            </div>
          )}

          {/* -- Form State -- */}
          {(acceptState === "form" || acceptState === "submitting") && (
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-semibold tracking-tight text-white">
                  Accept Invitation
                </h2>
                <p className="mt-2 text-sm font-light text-slate-400">
                  You have been invited to join the CSPM platform. Set your
                  password to complete your account setup.
                </p>
              </div>

              {errorMessage && (
                <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 backdrop-blur-sm">
                  <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/20">
                    <span className="text-xs font-bold text-red-400">!</span>
                  </div>
                  <p className="text-sm leading-relaxed text-red-300">
                    {errorMessage}
                  </p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Full Name */}
                <div>
                  <label
                    htmlFor="fullName"
                    className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                  >
                    Full Name
                  </label>
                  <div className="group relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <User
                        size={16}
                        className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                      />
                    </div>
                    <input
                      id="fullName"
                      type="text"
                      autoComplete="name"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="John Doe"
                    />
                  </div>
                </div>

                {/* Password */}
                <div>
                  <label
                    htmlFor="password"
                    className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                  >
                    Password
                  </label>
                  <div className="group relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Lock
                        size={16}
                        className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                      />
                    </div>
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (validationErrors.length > 0) {
                          setValidationErrors(validatePassword(e.target.value));
                        }
                      }}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-12 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="Create a strong password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-500 transition-colors hover:text-slate-300"
                      tabIndex={-1}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {validationErrors.length > 0 && (
                    <div className="mt-2 space-y-1">
                      <p className="text-xs text-slate-500">
                        Password must contain:
                      </p>
                      {validationErrors.map((err) => (
                        <p key={err} className="text-xs text-red-400">
                          - {err}
                        </p>
                      ))}
                    </div>
                  )}
                </div>

                {/* Confirm Password */}
                <div>
                  <label
                    htmlFor="confirmPassword"
                    className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                  >
                    Confirm Password
                  </label>
                  <div className="group relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Lock
                        size={16}
                        className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                      />
                    </div>
                    <input
                      id="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      minLength={8}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-12 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="Confirm your password"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowConfirmPassword(!showConfirmPassword)
                      }
                      className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-slate-500 transition-colors hover:text-slate-300"
                      tabIndex={-1}
                      aria-label={
                        showConfirmPassword ? "Hide password" : "Show password"
                      }
                    >
                      {showConfirmPassword ? (
                        <EyeOff size={16} />
                      ) : (
                        <Eye size={16} />
                      )}
                    </button>
                  </div>
                  {confirmPassword && password !== confirmPassword && (
                    <p className="mt-2 text-xs text-red-400">
                      Passwords do not match
                    </p>
                  )}
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={acceptState === "submitting"}
                  className="group relative mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    background:
                      acceptState === "submitting"
                        ? "linear-gradient(135deg, rgb(79,70,229) 0%, rgb(59,130,246) 100%)"
                        : "linear-gradient(135deg, rgb(99,102,241) 0%, rgb(59,130,246) 100%)",
                    boxShadow:
                      acceptState === "submitting"
                        ? "none"
                        : "0 0 20px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.3)",
                  }}
                >
                  {acceptState === "submitting" ? (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  ) : (
                    <>
                      <span>Create Account</span>
                      <ArrowRight
                        size={16}
                        className="transition-transform duration-300 group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </button>
              </form>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-600">
          <Lock size={12} />
          <span>256-bit TLS encrypted connection</span>
        </div>
      </div>
    </div>
  );
}
