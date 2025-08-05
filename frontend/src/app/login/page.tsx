"use client";

import { Suspense, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Shield,
  Mail,
  Lock,
  Eye,
  EyeOff,
  Scan,
  Zap,
  ArrowRight,
  Fingerprint,
  Globe,
} from "lucide-react";
import { useAuth, MfaRequiredError } from "@/lib/auth";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, completeMfaLogin } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // MFA state
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [useBackupCode, setUseBackupCode] = useState(false);

  // SSO state
  const [showSsoForm, setShowSsoForm] = useState(false);
  const [ssoSlug, setSsoSlug] = useState("");
  const [ssoLoading, setSsoLoading] = useState(false);

  // Show SSO error from callback redirect (e.g. domain restriction failure)
  useEffect(() => {
    const ssoError = searchParams.get("sso_error");
    if (ssoError) {
      setError(`SSO login failed: ${ssoError}`);
    }
  }, [searchParams]);

  const handleSsoLogin = () => {
    if (!ssoSlug.trim()) return;
    setSsoLoading(true);
    // Redirect to backend SSO authorize endpoint
    window.location.href = `/api/v1/auth/sso/authorize?tenant_slug=${encodeURIComponent(ssoSlug.trim())}`;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email, password });
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof MfaRequiredError) {
        setMfaToken(err.mfaToken);
      } else {
        setError("Invalid email or password. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMfaSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!mfaToken) return;
    setError(null);
    setIsSubmitting(true);

    try {
      await completeMfaLogin(mfaToken, mfaCode.trim());
      router.push("/dashboard");
    } catch {
      setError("Invalid verification code. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBackToLogin = () => {
    setMfaToken(null);
    setMfaCode("");
    setUseBackupCode(false);
    setError(null);
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-slate-950">
      {/* -- Animated grid background -- */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(99,102,241,0.12) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* -- Gradient overlay -- */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,27,75,0.9) 50%, rgba(15,23,42,0.95) 100%)",
        }}
      />

      {/* -- Noise texture overlay -- */}
      <div
        className="pointer-events-none absolute inset-0 z-0 opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* -- Ambient glow top-left -- */}
      <div
        className="pointer-events-none absolute -left-32 -top-32 z-0 h-[500px] w-[500px] rounded-full opacity-20 blur-[120px]"
        style={{
          background:
            "radial-gradient(circle, rgba(99,102,241,0.6) 0%, transparent 70%)",
        }}
      />

      {/* -- Ambient glow bottom-right -- */}
      <div
        className="pointer-events-none absolute -bottom-32 -right-32 z-0 h-[400px] w-[400px] rounded-full opacity-15 blur-[100px]"
        style={{
          background:
            "radial-gradient(circle, rgba(59,130,246,0.5) 0%, transparent 70%)",
        }}
      />

      {/* ============================== */}
      {/* LEFT PANEL - Hero / Branding   */}
      {/* ============================== */}
      <div className="relative z-10 hidden w-[60%] flex-col justify-between p-12 lg:flex xl:p-16">
        {/* Top: logo mark */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
            <Shield size={20} className="text-indigo-400" />
          </div>
          <span className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
            CSPM Platform
          </span>
        </div>

        {/* Center: hero content */}
        <div className="max-w-xl">
          {/* Animated shield icon */}
          <div className="relative mb-10 inline-flex">
            {/* Outer glow ring - pulsing */}
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background:
                  "radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)",
                animation: "shieldPulse 4s ease-in-out infinite",
                transform: "scale(2.5)",
              }}
            />
            {/* Inner glow ring */}
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background:
                  "radial-gradient(circle, rgba(99,102,241,0.25) 0%, transparent 60%)",
                animation: "shieldPulse 4s ease-in-out infinite 1s",
                transform: "scale(1.8)",
              }}
            />
            <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-indigo-500/20 bg-indigo-500/10 shadow-lg shadow-indigo-500/10">
              <Fingerprint size={40} className="text-indigo-400" />
            </div>
          </div>

          <h1 className="text-5xl font-bold tracking-tight text-white xl:text-6xl">
            <span className="block tracking-widest text-indigo-400">CSPM</span>
            <span className="mt-2 block text-2xl font-light tracking-wider text-slate-400 xl:text-3xl">
              Cloud Security Posture Management
            </span>
          </h1>

          <p className="mt-6 max-w-md text-base leading-relaxed text-slate-500">
            Unified visibility into your cloud security posture. Detect
            misconfigurations, enforce compliance, and remediate threats before
            they become incidents.
          </p>

          {/* Feature bullets */}
          <div className="mt-10 space-y-5">
            <FeatureBullet
              icon={<Shield size={18} />}
              text="80+ security controls across 30 resource types"
            />
            <FeatureBullet
              icon={<Scan size={18} />}
              text="Real-time compliance monitoring"
            />
            <FeatureBullet
              icon={<Zap size={18} />}
              text="Automated threat detection"
            />
          </div>
        </div>

        {/* Bottom: footer */}
        <div className="flex items-center gap-6 text-xs text-slate-600">
          <span>SOC 2 Type II</span>
          <span className="h-3 w-px bg-slate-700" />
          <span>CIS Benchmarks</span>
          <span className="h-3 w-px bg-slate-700" />
          <span>ISO 27001</span>
        </div>
      </div>

      {/* ============================== */}
      {/* RIGHT PANEL - Login Form       */}
      {/* ============================== */}
      <div className="relative z-10 flex w-full flex-col items-center justify-center px-6 py-12 lg:w-[40%] lg:px-12">
        {/* Mobile-only: compact hero */}
        <div className="mb-10 text-center lg:hidden">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-indigo-500/20 bg-indigo-500/10">
            <Shield size={28} className="text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold tracking-widest text-white uppercase">
            CSPM
          </h1>
          <p className="mt-1 text-sm font-light tracking-wider text-slate-400">
            Cloud Security Posture Management
          </p>
        </div>

        {/* Glass-morphic card */}
        <div className="w-full max-w-md">
          <div
            className="rounded-2xl border border-white/[0.08] p-8 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-10"
            style={{
              background:
                "linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
            }}
          >
            {/* Header */}
            <div className="mb-8">
              <h2 className="text-2xl font-semibold tracking-tight text-white">
                {mfaToken ? "Two-Factor Authentication" : "Welcome back"}
              </h2>
              <p className="mt-2 text-sm font-light text-slate-400">
                {mfaToken
                  ? useBackupCode
                    ? "Enter one of your backup codes"
                    : "Enter the 6-digit code from your authenticator app"
                  : "Sign in to your account to continue"}
              </p>
            </div>

            {/* Error state */}
            {error && (
              <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 backdrop-blur-sm">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/20">
                  <span className="text-xs font-bold text-red-400">!</span>
                </div>
                <p className="text-sm leading-relaxed text-red-300">{error}</p>
              </div>
            )}

            {/* MFA verification form */}
            {mfaToken ? (
              <form onSubmit={handleMfaSubmit} className="space-y-5">
                <div>
                  <label
                    htmlFor="mfa-code"
                    className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                  >
                    {useBackupCode ? "Backup code" : "Verification code"}
                  </label>
                  <div className="group relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Shield
                        size={16}
                        className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                      />
                    </div>
                    <input
                      id="mfa-code"
                      type="text"
                      inputMode={useBackupCode ? "text" : "numeric"}
                      autoComplete="one-time-code"
                      required
                      autoFocus
                      maxLength={useBackupCode ? 8 : 6}
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-4 text-sm tracking-widest text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder={useBackupCode ? "ABCD1234" : "000000"}
                    />
                  </div>
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="group relative mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    background: isSubmitting
                      ? "linear-gradient(135deg, rgb(79,70,229) 0%, rgb(59,130,246) 100%)"
                      : "linear-gradient(135deg, rgb(99,102,241) 0%, rgb(59,130,246) 100%)",
                    boxShadow: isSubmitting
                      ? "none"
                      : "0 0 20px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.3)",
                  }}
                >
                  {isSubmitting ? (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  ) : (
                    <>
                      <span>Verify</span>
                      <ArrowRight
                        size={16}
                        className="transition-transform duration-300 group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </button>

                {/* Toggle between TOTP and backup code */}
                <div className="flex items-center justify-between pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setUseBackupCode(!useBackupCode);
                      setMfaCode("");
                      setError(null);
                    }}
                    className="text-xs text-indigo-400 transition-colors hover:text-indigo-300"
                  >
                    {useBackupCode
                      ? "Use authenticator app"
                      : "Use a backup code"}
                  </button>
                  <button
                    type="button"
                    onClick={handleBackToLogin}
                    className="text-xs text-slate-500 transition-colors hover:text-slate-300"
                  >
                    Back to login
                  </button>
                </div>
              </form>
            ) : (
              /* Standard login form */
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Email field */}
                <div>
                  <label
                    htmlFor="email"
                    className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                  >
                    Email address
                  </label>
                  <div className="group relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Mail
                        size={16}
                        className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                      />
                    </div>
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="you@company.com"
                    />
                  </div>
                </div>

                {/* Password field */}
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
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-12 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="Enter your password"
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
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="group relative mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    background: isSubmitting
                      ? "linear-gradient(135deg, rgb(79,70,229) 0%, rgb(59,130,246) 100%)"
                      : "linear-gradient(135deg, rgb(99,102,241) 0%, rgb(59,130,246) 100%)",
                    boxShadow: isSubmitting
                      ? "none"
                      : "0 0 20px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.3)",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSubmitting) {
                      e.currentTarget.style.boxShadow =
                        "0 0 30px rgba(99,102,241,0.3), 0 8px 24px rgba(0,0,0,0.4)";
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow =
                      "0 0 20px rgba(99,102,241,0.15), 0 4px 12px rgba(0,0,0,0.3)";
                    e.currentTarget.style.transform = "translateY(0)";
                  }}
                >
                  {isSubmitting ? (
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  ) : (
                    <>
                      <span>Sign in</span>
                      <ArrowRight
                        size={16}
                        className="transition-transform duration-300 group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </button>
              </form>
            )}

            {/* SSO Divider */}
            {!mfaToken && (
              <>
                <div className="mt-8 flex items-center gap-3">
                  <div className="h-px flex-1 bg-white/[0.06]" />
                  <span className="text-[11px] tracking-widest text-slate-600 uppercase">
                    or
                  </span>
                  <div className="h-px flex-1 bg-white/[0.06]" />
                </div>

                {showSsoForm ? (
                  <div className="mt-5 space-y-3">
                    <div>
                      <label
                        htmlFor="sso-slug"
                        className="mb-2 block text-xs font-medium tracking-wider text-slate-400 uppercase"
                      >
                        Organization slug
                      </label>
                      <div className="group relative">
                        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                          <Globe
                            size={16}
                            className="text-slate-500 transition-colors group-focus-within:text-indigo-400"
                          />
                        </div>
                        <input
                          id="sso-slug"
                          type="text"
                          autoFocus
                          required
                          value={ssoSlug}
                          onChange={(e) => setSsoSlug(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              handleSsoLogin();
                            }
                          }}
                          className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                          placeholder="your-company"
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleSsoLogin}
                      disabled={ssoLoading || !ssoSlug.trim()}
                      className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-sm font-medium text-slate-300 transition-all duration-200 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {ssoLoading ? (
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      ) : (
                        <>
                          <Globe size={16} className="text-indigo-400" />
                          <span>Continue with SSO</span>
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowSsoForm(false);
                        setSsoSlug("");
                      }}
                      className="w-full text-center text-xs text-slate-500 transition-colors hover:text-slate-300"
                    >
                      Back to email login
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowSsoForm(true)}
                    className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-sm font-medium text-slate-300 transition-all duration-200 hover:bg-white/[0.08]"
                  >
                    <Globe size={16} className="text-indigo-400" />
                    <span>Sign in with SSO</span>
                  </button>
                )}
              </>
            )}

            {/* Divider */}
            <div className="mt-8 flex items-center gap-3">
              <div className="h-px flex-1 bg-white/[0.06]" />
              <span className="text-[11px] tracking-widest text-slate-600 uppercase">
                Secured Access
              </span>
              <div className="h-px flex-1 bg-white/[0.06]" />
            </div>

            {/* Security note */}
            <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-600">
              <Lock size={12} />
              <span>256-bit TLS encrypted connection</span>
            </div>
          </div>
        </div>
      </div>

      {/* -- Keyframe animations -- */}
      <style>{`
        @keyframes shieldPulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

/* -- Feature Bullet sub-component -- */
function FeatureBullet({
  icon,
  text,
}: {
  icon: React.ReactNode;
  text: string;
}) {
  return (
    <div className="flex items-center gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-indigo-500/15 bg-indigo-500/10 text-indigo-400">
        {icon}
      </div>
      <span className="text-sm text-slate-300">{text}</span>
    </div>
  );
}
