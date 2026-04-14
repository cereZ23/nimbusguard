"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { Shield, Mail, ArrowRight, ArrowLeft, Lock } from "lucide-react";
import api from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await api.post("/auth/forgot-password", { email });
      setSubmitted(true);
    } catch {
      // The backend always returns 204, but network errors can still happen
      setError("An error occurred. Please try again later.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
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

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10 ring-1 ring-indigo-500/20">
            <Shield size={20} className="text-indigo-400" />
          </div>
          <span className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
            PostureOne
          </span>
        </div>

        {/* Glass-morphic card */}
        <div
          className="rounded-2xl border border-white/[0.08] p-8 shadow-2xl shadow-black/40 backdrop-blur-xl sm:p-10"
          style={{
            background:
              "linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)",
          }}
        >
          {submitted ? (
            /* Success state */
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10">
                <Mail size={24} className="text-emerald-400" />
              </div>
              <h2 className="text-xl font-semibold tracking-tight text-white">
                Check your email
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                If an account exists with this email, you will receive a
                password reset link. Please check your inbox and spam folder.
              </p>
              <Link
                href="/login"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-indigo-400 transition-colors hover:text-indigo-300"
              >
                <ArrowLeft size={16} />
                <span>Back to login</span>
              </Link>
            </div>
          ) : (
            /* Form state */
            <>
              <div className="mb-8">
                <h2 className="text-2xl font-semibold tracking-tight text-white">
                  Forgot password?
                </h2>
                <p className="mt-2 text-sm font-light text-slate-400">
                  Enter your email address and we will send you a link to reset
                  your password.
                </p>
              </div>

              {/* Error state */}
              {error && (
                <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 backdrop-blur-sm">
                  <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/20">
                    <span className="text-xs font-bold text-red-400">!</span>
                  </div>
                  <p className="text-sm leading-relaxed text-red-300">
                    {error}
                  </p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
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
                      autoFocus
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="block w-full rounded-xl border border-white/[0.08] bg-white/[0.04] py-3 pl-10 pr-4 text-sm text-white placeholder:text-slate-500 transition-all duration-200 focus:border-indigo-500/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-indigo-500/30"
                      placeholder="you@company.com"
                    />
                  </div>
                </div>

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
                      <span>Send Reset Link</span>
                      <ArrowRight
                        size={16}
                        className="transition-transform duration-300 group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-6 text-center">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 text-sm text-indigo-400 transition-colors hover:text-indigo-300"
                >
                  <ArrowLeft size={14} />
                  <span>Back to login</span>
                </Link>
              </div>
            </>
          )}
        </div>

        {/* Security note */}
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-600">
          <Lock size={12} />
          <span>256-bit TLS encrypted connection</span>
        </div>
      </div>
    </div>
  );
}
