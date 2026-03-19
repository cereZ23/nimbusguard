"use client";

import { useState } from "react";
import { Shield, Plus, Building2, CheckCircle } from "lucide-react";
import api from "@/lib/api";
import { extractApiError } from "@/lib/errors";
import Button from "@/components/ui/button";
import Input from "@/components/ui/input";
import Modal from "@/components/ui/modal";

interface CreatedTenant {
  email: string;
  password: string;
  tenant_name: string;
}

export default function AdminTenantsPage() {
  const [showModal, setShowModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedTenant | null>(null);

  const [tenantName, setTenantName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminName, setAdminName] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  const resetForm = () => {
    setTenantName("");
    setAdminEmail("");
    setAdminName("");
    setAdminPassword("");
    setError(null);
  };

  const handleCreate = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      await api.post("/auth/register", {
        email: adminEmail,
        password: adminPassword,
        full_name: adminName,
        tenant_name: tenantName,
      });
      setCreated({
        email: adminEmail,
        password: adminPassword,
        tenant_name: tenantName,
      });
      setShowModal(false);
      resetForm();
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-gray-900">
      <div className="w-full max-w-xl">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-indigo-50 dark:bg-indigo-900/30">
            <Shield
              size={28}
              className="text-indigo-600 dark:text-indigo-400"
            />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            PostureOne Admin
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Tenant provisioning panel
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Create New Tenant
            </h2>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setShowModal(true);
                setCreated(null);
              }}
            >
              <Plus size={16} />
              New Tenant
            </Button>
          </div>

          <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
            Each tenant is an isolated organization with its own cloud accounts,
            users, findings, and settings. Creating a tenant also creates the
            first admin user who can then invite others.
          </p>

          {created && (
            <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-5 dark:border-green-700 dark:bg-green-900/20">
              <div className="flex items-start gap-3">
                <CheckCircle
                  size={20}
                  className="mt-0.5 shrink-0 text-green-600 dark:text-green-400"
                />
                <div>
                  <p className="font-medium text-green-800 dark:text-green-300">
                    Tenant created successfully
                  </p>
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Building2
                        size={14}
                        className="text-green-600 dark:text-green-400"
                      />
                      <span className="text-green-700 dark:text-green-300">
                        <strong>Tenant:</strong> {created.tenant_name}
                      </span>
                    </div>
                    <div>
                      <strong className="text-green-700 dark:text-green-300">
                        Admin email:
                      </strong>{" "}
                      <code className="rounded bg-green-100 px-1.5 py-0.5 text-xs dark:bg-green-800">
                        {created.email}
                      </code>
                    </div>
                    <div>
                      <strong className="text-green-700 dark:text-green-300">
                        Password:
                      </strong>{" "}
                      <code className="rounded bg-green-100 px-1.5 py-0.5 text-xs dark:bg-green-800">
                        {created.password}
                      </code>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-green-600 dark:text-green-400">
                    Share these credentials with the tenant admin. They can
                    change their password after first login.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-gray-400 dark:text-gray-500">
          This page is not linked from the main app. Bookmark it or access via
          /admin/tenants.
        </p>
      </div>

      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title="Create New Tenant"
        size="md"
      >
        <div className="space-y-4">
          <Input
            label="Organization Name"
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            placeholder="e.g. Acme Corp"
          />
          <Input
            label="Admin Full Name"
            value={adminName}
            onChange={(e) => setAdminName(e.target.value)}
            placeholder="e.g. John Doe"
          />
          <Input
            label="Admin Email"
            type="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder="admin@acme.com"
          />
          <Input
            label="Admin Password"
            type="password"
            value={adminPassword}
            onChange={(e) => setAdminPassword(e.target.value)}
            placeholder="Min 8 chars, uppercase, number, special"
            error={error || undefined}
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={isSubmitting}
              disabled={
                !tenantName.trim() ||
                !adminEmail.trim() ||
                !adminName.trim() ||
                !adminPassword.trim()
              }
              onClick={handleCreate}
            >
              Create Tenant
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
