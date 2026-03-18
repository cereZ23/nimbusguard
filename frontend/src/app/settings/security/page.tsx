"use client";

import { useCallback, useRef, useState } from "react";
import { Check, Copy, Shield, X } from "lucide-react";
import Button from "@/components/ui/button";
import BrandingSection from "@/components/settings/branding-section";
import ScimSection from "@/components/settings/scim-section";
import SsoSection from "@/components/settings/sso-section";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import type { MfaSetupResponse } from "@/types";

export default function SecurityPage() {
  // -- Branding --
  const { branding, refresh: refreshBranding } = useBranding();
  const [brandingForm, setBrandingForm] = useState<{
    company_name: string;
    primary_color: string;
  }>({ company_name: "", primary_color: "" });
  const [brandingInitialized, setBrandingInitialized] = useState(false);
  const [brandingSaving, setBrandingSaving] = useState(false);
  const [brandingError, setBrandingError] = useState<string | null>(null);
  const [brandingSuccess, setBrandingSuccess] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);

  // Initialize branding form when branding data loads
  if (!brandingInitialized && branding.company_name) {
    setBrandingForm({
      company_name: branding.company_name,
      primary_color: branding.primary_color,
    });
    setBrandingInitialized(true);
  }

  const handleBrandingSave = useCallback(async () => {
    setBrandingSaving(true);
    setBrandingError(null);
    setBrandingSuccess(false);
    try {
      const payload: Record<string, string> = {};
      if (brandingForm.company_name !== branding.company_name) {
        payload.company_name = brandingForm.company_name;
      }
      if (brandingForm.primary_color !== branding.primary_color) {
        payload.primary_color = brandingForm.primary_color;
      }
      if (Object.keys(payload).length > 0) {
        await api.put("/branding", payload);
        await refreshBranding();
      }
      setBrandingSuccess(true);
      setTimeout(() => setBrandingSuccess(false), 3000);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { data?: { error?: string; detail?: string } };
      };
      setBrandingError(
        axiosErr.response?.data?.error ??
          axiosErr.response?.data?.detail ??
          "Failed to save branding.",
      );
      setTimeout(() => setBrandingError(null), 5000);
    } finally {
      setBrandingSaving(false);
    }
  }, [brandingForm, branding, refreshBranding]);

  const handleLogoUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const allowedTypes = ["image/png", "image/jpeg", "image/svg+xml"];
      if (!allowedTypes.includes(file.type)) {
        setLogoError("Invalid file type. Allowed: PNG, JPG, SVG.");
        setTimeout(() => setLogoError(null), 5000);
        return;
      }
      if (file.size > 500 * 1024) {
        setLogoError("File too large. Max: 500 KB.");
        setTimeout(() => setLogoError(null), 5000);
        return;
      }

      setLogoUploading(true);
      setLogoError(null);
      try {
        const formData = new FormData();
        formData.append("file", file);
        await api.post("/branding/logo", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        await refreshBranding();
      } catch (err: unknown) {
        const axiosErr = err as {
          response?: { data?: { error?: string; detail?: string } };
        };
        setLogoError(
          axiosErr.response?.data?.error ??
            axiosErr.response?.data?.detail ??
            "Failed to upload logo.",
        );
        setTimeout(() => setLogoError(null), 5000);
      } finally {
        setLogoUploading(false);
        if (logoInputRef.current) {
          logoInputRef.current.value = "";
        }
      }
    },
    [refreshBranding],
  );

  const isColorValid = /^#[0-9a-fA-F]{6}$/.test(brandingForm.primary_color);

  // -- MFA state --
  const { user } = useAuth();
  const [mfaSetupData, setMfaSetupData] = useState<MfaSetupResponse | null>(
    null,
  );
  const [mfaBackupCodes, setMfaBackupCodes] = useState<string[] | null>(null);
  const [mfaVerifyCode, setMfaVerifyCode] = useState("");
  const [mfaDisablePassword, setMfaDisablePassword] = useState("");
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [mfaSuccess, setMfaSuccess] = useState<string | null>(null);
  const [showMfaSetup, setShowMfaSetup] = useState(false);
  const [showMfaDisable, setShowMfaDisable] = useState(false);
  const [copiedBackupCodes, setCopiedBackupCodes] = useState(false);

  const handleMfaSetup = async () => {
    setMfaLoading(true);
    setMfaError(null);
    try {
      const res = await api.post("/auth/mfa/setup");
      setMfaSetupData(res.data.data as MfaSetupResponse);
      setShowMfaSetup(true);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setMfaError(
        axiosErr.response?.data?.detail ?? "Failed to start MFA setup.",
      );
    } finally {
      setMfaLoading(false);
    }
  };

  const handleMfaVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setMfaLoading(true);
    setMfaError(null);
    try {
      const res = await api.post("/auth/mfa/verify", { code: mfaVerifyCode });
      const data = res.data.data as { backup_codes: string[] };
      setMfaBackupCodes(data.backup_codes);
      setShowMfaSetup(false);
      setMfaSetupData(null);
      setMfaVerifyCode("");
      setMfaSuccess("Two-factor authentication has been enabled.");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setMfaError(
        axiosErr.response?.data?.detail ?? "Invalid verification code.",
      );
    } finally {
      setMfaLoading(false);
    }
  };

  const handleMfaDisable = async (e: React.FormEvent) => {
    e.preventDefault();
    setMfaLoading(true);
    setMfaError(null);
    try {
      await api.post("/auth/mfa/disable", { password: mfaDisablePassword });
      setShowMfaDisable(false);
      setMfaDisablePassword("");
      setMfaSuccess("Two-factor authentication has been disabled.");
      // Refresh page to update user state
      window.location.reload();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setMfaError(
        axiosErr.response?.data?.detail ??
          "Failed to disable MFA. Check your password.",
      );
    } finally {
      setMfaLoading(false);
    }
  };

  const handleCopyBackupCodes = async () => {
    if (!mfaBackupCodes) return;
    await navigator.clipboard.writeText(mfaBackupCodes.join("\n"));
    setCopiedBackupCodes(true);
    setTimeout(() => setCopiedBackupCodes(false), 2000);
  };

  return (
    <>
      {/* Two-Factor Authentication */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Two-Factor Authentication
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Add an extra layer of security to your account
              </p>
            </div>
            {user?.mfa_enabled && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                <Check size={14} /> Enabled
              </span>
            )}
          </div>
        </div>
        <div className="px-6 py-4">
          {mfaError && (
            <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {mfaError}
            </div>
          )}
          {mfaSuccess && !mfaBackupCodes && (
            <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
              {mfaSuccess}
            </div>
          )}
          {mfaBackupCodes && (
            <div className="mb-4 space-y-3">
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-900/20">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                  Save your backup codes
                </p>
                <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                  These codes can be used to access your account if you lose
                  your authenticator device. Each code can only be used once.
                </p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 font-mono text-sm dark:border-gray-600 dark:bg-gray-700">
                <div className="grid grid-cols-2 gap-2">
                  {mfaBackupCodes.map((code) => (
                    <span
                      key={code}
                      className="text-gray-800 dark:text-gray-200"
                    >
                      {code}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCopyBackupCodes}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                >
                  {copiedBackupCodes ? <Check size={14} /> : <Copy size={14} />}
                  {copiedBackupCodes ? "Copied" : "Copy codes"}
                </button>
                <button
                  onClick={() => {
                    setMfaBackupCodes(null);
                    setMfaSuccess(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                >
                  I have saved my codes
                </button>
              </div>
            </div>
          )}
          {showMfaSetup && mfaSetupData && (
            <div className="mb-4 space-y-4">
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Scan the QR code below with your authenticator app (Google
                Authenticator, Authy, 1Password, etc.):
              </p>
              <div className="flex justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl=${encodeURIComponent(mfaSetupData.provisioning_uri)}`}
                  alt="MFA QR Code"
                  width={200}
                  height={200}
                  className="rounded-lg"
                />
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-600 dark:bg-gray-700">
                <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                  Or enter this key manually:
                </p>
                <p className="select-all font-mono text-sm font-medium tracking-wider text-gray-800 dark:text-gray-200">
                  {mfaSetupData.secret}
                </p>
              </div>
              <form onSubmit={handleMfaVerify} className="space-y-3">
                <div>
                  <label
                    htmlFor="mfa-verify-code"
                    className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Enter the 6-digit code from your app
                  </label>
                  <input
                    id="mfa-verify-code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={mfaVerifyCode}
                    onChange={(e) => setMfaVerifyCode(e.target.value)}
                    className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm tracking-widest text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    placeholder="000000"
                    required
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={mfaVerifyCode.trim().length !== 6}
                    loading={mfaLoading}
                  >
                    <Check size={14} />
                    Verify and enable
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setShowMfaSetup(false);
                      setMfaSetupData(null);
                      setMfaVerifyCode("");
                      setMfaError(null);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </div>
          )}
          {showMfaDisable && (
            <div className="mb-4">
              <form onSubmit={handleMfaDisable} className="space-y-3">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  Enter your password to disable two-factor authentication:
                </p>
                <input
                  type="password"
                  value={mfaDisablePassword}
                  onChange={(e) => setMfaDisablePassword(e.target.value)}
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder="Your password"
                  required
                />
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    variant="danger"
                    disabled={!mfaDisablePassword}
                    loading={mfaLoading}
                  >
                    <X size={14} />
                    Disable 2FA
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      setShowMfaDisable(false);
                      setMfaDisablePassword("");
                      setMfaError(null);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            </div>
          )}
          {!showMfaSetup && !showMfaDisable && !mfaBackupCodes && (
            <div>
              {user?.mfa_enabled ? (
                <button
                  onClick={() => {
                    setShowMfaDisable(true);
                    setMfaError(null);
                    setMfaSuccess(null);
                  }}
                  className="flex items-center gap-1.5 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-800 dark:bg-gray-700 dark:text-red-400"
                >
                  <X size={14} /> Disable 2FA
                </button>
              ) : (
                <Button
                  variant="primary"
                  onClick={handleMfaSetup}
                  loading={mfaLoading}
                >
                  <Shield size={14} />
                  Enable 2FA
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Branding */}
      <BrandingSection
        branding={branding}
        brandingForm={brandingForm}
        setBrandingForm={setBrandingForm}
        isColorValid={isColorValid}
        logoInputRef={logoInputRef}
        handleLogoUpload={handleLogoUpload}
        logoUploading={logoUploading}
        logoError={logoError}
        handleBrandingSave={handleBrandingSave}
        brandingSaving={brandingSaving}
        brandingSuccess={brandingSuccess}
        brandingError={brandingError}
      />

      {/* Single Sign-On (SSO) */}
      <SsoSection />

      {/* SCIM Provisioning */}
      <ScimSection />
    </>
  );
}
