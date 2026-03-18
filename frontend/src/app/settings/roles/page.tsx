"use client";

import { useState } from "react";
import useSWR from "swr";
import { Pencil, Plus, Shield, Trash2, X } from "lucide-react";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { PermissionListResponse, Role } from "@/types";

export default function RolesPage() {
  const {
    data: rolesEnvelope,
    error: rolesError,
    isLoading: rolesLoading,
    mutate: mutateRoles,
  } = useSWR("/roles");

  const { data: permissionsEnvelope } = useSWR("/roles/permissions");

  const roles = (rolesEnvelope?.data ?? []) as Role[];
  const permissionsCatalog = permissionsEnvelope?.data as
    | PermissionListResponse
    | undefined;

  const error = rolesError?.message ?? rolesEnvelope?.error ?? null;

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // -- Role management state --
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [roleForm, setRoleForm] = useState({
    name: "",
    description: "",
    permissions: [] as string[],
  });

  const handleOpenCreateRole = () => {
    setEditingRole(null);
    setRoleForm({ name: "", description: "", permissions: [] });
    setFormError(null);
    setShowRoleModal(true);
  };

  const handleOpenEditRole = (role: Role) => {
    setEditingRole(role);
    setRoleForm({
      name: role.name,
      description: role.description ?? "",
      permissions: [...role.permissions],
    });
    setFormError(null);
    setShowRoleModal(true);
  };

  const toggleRolePermission = (perm: string) => {
    setRoleForm((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(perm)
        ? prev.permissions.filter((p) => p !== perm)
        : [...prev.permissions, perm],
    }));
  };

  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      if (editingRole) {
        await api.put(`/roles/${editingRole.id}`, {
          name: roleForm.name,
          description: roleForm.description || null,
          permissions: roleForm.permissions,
        });
      } else {
        await api.post("/roles", {
          name: roleForm.name,
          description: roleForm.description || null,
          permissions: roleForm.permissions,
        });
      }
      setShowRoleModal(false);
      setEditingRole(null);
      mutateRoles();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(axiosErr.response?.data?.detail ?? "Failed to save role.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteRole = async (roleId: string, roleName: string) => {
    if (
      !window.confirm(
        `Delete role "${roleName}"? Users with this role will lose their custom permissions.`,
      )
    )
      return;
    setActionError(null);
    try {
      await api.delete(`/roles/${roleId}`);
      mutateRoles();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete role.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  return (
    <>
      {/* Action buttons */}
      <div className="flex justify-end">
        <button
          onClick={handleOpenCreateRole}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus size={16} />
          Create Role
        </button>
      </div>

      {/* Error state for initial load */}
      {error && <ErrorState message={error} onRetry={() => mutateRoles()} />}

      {/* Action error banner */}
      {actionError && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {actionError}
        </div>
      )}

      {!error && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Roles & Permissions
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Define custom roles with granular permissions
            </p>
          </div>

          {rolesLoading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {roles.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between px-6 py-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                      <Shield size={16} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {r.name}
                        </p>
                        {r.is_system && (
                          <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                            System
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {r.description ?? "No description"}
                        {" -- "}
                        {r.permissions.includes("*")
                          ? "All permissions"
                          : `${r.permissions.length} permission${r.permissions.length !== 1 ? "s" : ""}`}
                      </p>
                    </div>
                  </div>
                  {!r.is_system && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleOpenEditRole(r)}
                        className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-blue-900/20"
                        title="Edit role"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => handleDeleteRole(r.id, r.name)}
                        className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                        title="Delete role"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {roles.length === 0 && (
                <div className="flex items-center justify-center py-8 text-sm text-gray-500 dark:text-gray-400">
                  <Shield size={16} className="mr-2" />
                  No roles configured. System roles (Admin, Viewer) are always
                  available.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Role Create/Edit Modal */}
      {showRoleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {editingRole ? "Edit Role" : "Create Role"}
              </h2>
              <button
                onClick={() => {
                  setShowRoleModal(false);
                  setEditingRole(null);
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSaveRole} className="space-y-4">
              <div>
                <label
                  htmlFor="role_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Role Name
                </label>
                <input
                  id="role_name"
                  type="text"
                  required
                  maxLength={50}
                  value={roleForm.name}
                  onChange={(e) =>
                    setRoleForm((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="e.g. Security Analyst"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label
                  htmlFor="role_desc"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Description
                </label>
                <textarea
                  id="role_desc"
                  rows={2}
                  value={roleForm.description}
                  onChange={(e) =>
                    setRoleForm((p) => ({ ...p, description: e.target.value }))
                  }
                  placeholder="Brief description of this role"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Permissions
                </label>
                <div className="max-h-64 space-y-4 overflow-y-auto rounded-lg border border-gray-200 p-3 dark:border-gray-600">
                  {permissionsCatalog?.categories &&
                    Object.entries(permissionsCatalog.categories).map(
                      ([category, perms]) => (
                        <div key={category}>
                          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                            {category}
                          </p>
                          <div className="space-y-1">
                            {perms.map((perm) => {
                              const info = permissionsCatalog.permissions.find(
                                (p) => p.permission === perm,
                              );
                              return (
                                <label
                                  key={perm}
                                  className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-700"
                                >
                                  <input
                                    type="checkbox"
                                    checked={roleForm.permissions.includes(
                                      perm,
                                    )}
                                    onChange={() => toggleRolePermission(perm)}
                                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                  />
                                  <span className="text-sm text-gray-900 dark:text-gray-100">
                                    {info?.description ?? perm}
                                  </span>
                                  <span className="ml-auto font-mono text-xs text-gray-400">
                                    {perm}
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      ),
                    )}
                </div>
                {roleForm.permissions.length === 0 && (
                  <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                    Select at least one permission
                  </p>
                )}
              </div>
              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowRoleModal(false);
                    setEditingRole(null);
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || roleForm.permissions.length === 0}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting
                    ? "Saving..."
                    : editingRole
                      ? "Update Role"
                      : "Create Role"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
