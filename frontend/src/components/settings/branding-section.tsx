"use client";

import Image from "next/image";
import { Check, Paintbrush, Shield, Upload } from "lucide-react";
import type { TenantBranding } from "@/types";

interface BrandingSectionProps {
  branding: TenantBranding;
  brandingForm: { company_name: string; primary_color: string };
  setBrandingForm: React.Dispatch<
    React.SetStateAction<{ company_name: string; primary_color: string }>
  >;
  isColorValid: boolean;
  logoInputRef: React.RefObject<HTMLInputElement | null>;
  handleLogoUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  logoUploading: boolean;
  logoError: string | null;
  handleBrandingSave: () => void;
  brandingSaving: boolean;
  brandingSuccess: boolean;
  brandingError: string | null;
}

export default function BrandingSection({
  branding,
  brandingForm,
  setBrandingForm,
  isColorValid,
  logoInputRef,
  handleLogoUpload,
  logoUploading,
  logoError,
  handleBrandingSave,
  brandingSaving,
  brandingSuccess,
  brandingError,
}: BrandingSectionProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Paintbrush size={20} className="text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Branding
          </h2>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Customize the look and feel with your company logo and colors
        </p>
      </div>

      <div className="space-y-6 px-6 py-5">
        {/* Logo upload */}
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
            Logo
          </label>
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-600 dark:bg-gray-700">
              {branding.logo_url ? (
                <Image
                  src={branding.logo_url}
                  alt="Tenant logo"
                  width={64}
                  height={64}
                  className="h-full w-full object-contain"
                  unoptimized
                />
              ) : (
                <Shield
                  size={28}
                  className="text-gray-400 dark:text-gray-500"
                />
              )}
            </div>
            <div>
              <input
                ref={logoInputRef}
                type="file"
                accept="image/png,image/jpeg,image/svg+xml"
                onChange={handleLogoUpload}
                className="hidden"
                id="logo-upload"
              />
              <button
                onClick={() => logoInputRef.current?.click()}
                disabled={logoUploading}
                className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
              >
                <Upload size={14} />
                {logoUploading ? "Uploading..." : "Upload logo"}
              </button>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                PNG, JPG, or SVG. Max 500 KB.
              </p>
            </div>
          </div>
          {logoError && (
            <p className="mt-2 text-sm text-red-600 dark:text-red-400">
              {logoError}
            </p>
          )}
        </div>

        {/* Company name */}
        <div>
          <label
            htmlFor="branding-company-name"
            className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Company name
          </label>
          <input
            id="branding-company-name"
            type="text"
            maxLength={100}
            value={brandingForm.company_name}
            onChange={(e) =>
              setBrandingForm((prev) => ({
                ...prev,
                company_name: e.target.value,
              }))
            }
            className="w-full max-w-sm rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
            placeholder="CSPM"
          />
        </div>

        {/* Primary color */}
        <div>
          <label
            htmlFor="branding-primary-color"
            className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Primary color
          </label>
          <div className="flex items-center gap-3">
            <div
              className="h-10 w-10 shrink-0 rounded-lg border border-gray-300 dark:border-gray-600"
              style={{
                backgroundColor: isColorValid
                  ? brandingForm.primary_color
                  : "#ccc",
              }}
            />
            <input
              id="branding-primary-color"
              type="text"
              value={brandingForm.primary_color}
              onChange={(e) =>
                setBrandingForm((prev) => ({
                  ...prev,
                  primary_color: e.target.value,
                }))
              }
              className={`w-36 rounded-lg border bg-white px-3 py-2 font-mono text-sm shadow-sm focus:outline-none dark:bg-gray-800 dark:text-gray-200 ${
                isColorValid
                  ? "border-gray-300 focus:border-blue-500 dark:border-gray-600"
                  : "border-red-400 dark:border-red-500"
              }`}
              placeholder="#6366f1"
            />
            <input
              type="color"
              value={isColorValid ? brandingForm.primary_color : "#6366f1"}
              onChange={(e) =>
                setBrandingForm((prev) => ({
                  ...prev,
                  primary_color: e.target.value,
                }))
              }
              className="h-10 w-10 cursor-pointer rounded border-0 bg-transparent p-0"
              title="Pick a color"
            />
          </div>
          {!isColorValid && brandingForm.primary_color.length > 0 && (
            <p className="mt-1 text-xs text-red-500">
              Enter a valid hex color (e.g. #6366f1)
            </p>
          )}
        </div>

        {/* Sidebar preview */}
        <div>
          <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
            Preview
          </label>
          <div className="inline-flex items-center gap-3 rounded-lg bg-slate-900 px-4 py-3">
            <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg ring-1 ring-white/20">
              {branding.logo_url ? (
                <Image
                  src={branding.logo_url}
                  alt="Preview"
                  width={36}
                  height={36}
                  className="h-full w-full object-contain"
                  unoptimized
                />
              ) : (
                <Shield
                  size={20}
                  style={{
                    color: isColorValid
                      ? brandingForm.primary_color
                      : "#6366f1",
                  }}
                />
              )}
            </div>
            <span
              className="text-[15px] font-bold tracking-widest"
              style={{
                color: isColorValid ? brandingForm.primary_color : "#6366f1",
              }}
            >
              {brandingForm.company_name || "CSPM"}
            </span>
          </div>
        </div>

        {/* Save button + feedback */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleBrandingSave}
            disabled={brandingSaving || !isColorValid}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {brandingSaving ? "Saving..." : "Save branding"}
          </button>
          {brandingSuccess && (
            <span className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
              <Check size={14} /> Saved
            </span>
          )}
          {brandingError && (
            <span className="text-sm text-red-600 dark:text-red-400">
              {brandingError}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
