"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Check,
  Clock,
  Copy,
  RefreshCw,
  Trash2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Button from "@/components/ui/button";
import ConfirmDialog from "@/components/ui/confirm-dialog";
import Modal from "@/components/ui/modal";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import type { Invitation, InvitationCreated, Role, TenantUser } from "@/types";

export default function UsersPage() {
  const {
    data: usersEnvelope,
    error: usersError,
    isLoading: usersLoading,
    mutate: mutateUsers,
  } = useSWR("/users");

  const {
    data: rolesEnvelope,
    error: rolesError,
    isLoading: rolesLoading,
    mutate: mutateRoles,
  } = useSWR("/roles");

  const { data: invitationsEnvelope, mutate: mutateInvitations } =
    useSWR("/invitations");

  const users = (usersEnvelope?.data ?? []) as TenantUser[];
  const roles = (rolesEnvelope?.data ?? []) as Role[];
  const invitations = (invitationsEnvelope?.data ?? []) as Invitation[];
  const pendingInvitations = invitations.filter(
    (inv) => inv.status === "pending",
  );

  const isLoading = usersLoading || rolesLoading;
  const error =
    usersError?.message ??
    rolesError?.message ??
    usersEnvelope?.error ??
    rolesEnvelope?.error ??
    null;

  const handleRetry = () => {
    mutateUsers();
    mutateRoles();
    mutateInvitations();
  };

  const [actionError, setActionError] = useState<string | null>(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteForm, setInviteForm] = useState({
    email: "",
    role: "viewer",
  });
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);
  const [copiedInviteUrl, setCopiedInviteUrl] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      const res = await api.post("/invitations", {
        email: inviteForm.email,
        role: inviteForm.role,
      });
      const created = res.data.data as InvitationCreated;
      setLastInviteUrl(created.invite_url);
      setInviteForm({ email: "", role: "viewer" });
      mutateInvitations();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to send invitation.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyInviteUrl = async (url: string) => {
    await navigator.clipboard.writeText(url);
    setCopiedInviteUrl(true);
    setTimeout(() => setCopiedInviteUrl(false), 2000);
  };

  const [deleteTarget, setDeleteTarget] = useState<{
    type: "user" | "invitation";
    id: string;
    label: string;
  } | null>(null);

  const handleRevokeInvitation = async (invitationId: string) => {
    setActionError(null);
    try {
      await api.delete(`/invitations/${invitationId}`);
      mutateInvitations();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to revoke invitation.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleResendInvitation = async (invitationId: string) => {
    setActionError(null);
    try {
      const res = await api.post("/invitations/resend", {
        invitation_id: invitationId,
      });
      const resent = res.data.data as { invite_url: string };
      setLastInviteUrl(resent.invite_url);
      setShowInviteModal(true);
      mutateInvitations();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to resend invitation.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleChangeRole = async (userId: string, roleValue: string) => {
    setActionError(null);
    try {
      const isSystemRole = roleValue === "admin" || roleValue === "viewer";
      if (isSystemRole) {
        await api.put(`/users/${userId}/role`, {
          role: roleValue,
          role_id: null,
        });
      } else {
        await api.put(`/users/${userId}/role`, { role_id: roleValue });
      }
      mutateUsers();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to update user role.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const getUserRoleValue = (u: TenantUser): string => {
    if (u.role_id) return u.role_id;
    return u.role;
  };

  const handleRemoveUser = async (userId: string) => {
    setActionError(null);
    try {
      await api.delete(`/users/${userId}`);
      mutateUsers(
        (current: typeof usersEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as TenantUser[]).filter((u) => u.id !== userId),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to remove user.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  return (
    <>
      {/* Action buttons */}
      <div className="flex justify-end">
        <Button variant="primary" onClick={() => setShowInviteModal(true)}>
          <UserPlus size={16} />
          Invite User
        </Button>
      </div>

      {/* Error state for initial load */}
      {error && <ErrorState message={error} onRetry={handleRetry} />}

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
              Team Members
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Manage users and roles for your tenant
            </p>
          </div>

          {isLoading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
            </div>
          ) : (
            <>
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {users.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">
                        {u.full_name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {u.full_name}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {u.email}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <select
                        value={getUserRoleValue(u)}
                        onChange={(e) => handleChangeRole(u.id, e.target.value)}
                        className="rounded-lg border border-gray-300 bg-white px-2 py-1 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      >
                        <optgroup label="System Roles">
                          <option value="admin">Administrator</option>
                          <option value="viewer">Viewer</option>
                        </optgroup>
                        {roles.filter((r) => !r.is_system).length > 0 && (
                          <optgroup label="Custom Roles">
                            {roles
                              .filter((r) => !r.is_system)
                              .map((r) => (
                                <option key={r.id} value={r.id}>
                                  {r.name}
                                </option>
                              ))}
                          </optgroup>
                        )}
                      </select>
                      <button
                        onClick={() =>
                          setDeleteTarget({
                            type: "user",
                            id: u.id,
                            label: u.email,
                          })
                        }
                        className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
                        title="Remove user"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
                {users.length === 0 && (
                  <div className="flex items-center justify-center py-8 text-sm text-gray-500">
                    <Users size={16} className="mr-2" />
                    No team members found.
                  </div>
                )}
              </div>

              {/* Pending Invitations */}
              {pendingInvitations.length > 0 && (
                <div className="border-t border-gray-200 dark:border-gray-700">
                  <div className="px-6 py-3">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Pending Invitations ({pendingInvitations.length})
                    </h3>
                  </div>
                  <div className="divide-y divide-gray-100 dark:divide-gray-700">
                    {pendingInvitations.map((inv) => (
                      <div
                        key={inv.id}
                        className="flex items-center justify-between px-6 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-sm font-semibold text-amber-700">
                            <Clock size={16} />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900 dark:text-gray-100">
                              {inv.email}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Invited as {inv.role} — expires{" "}
                              {new Date(inv.expires_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleResendInvitation(inv.id)}
                            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-blue-900/20"
                            title="Resend invitation"
                          >
                            <RefreshCw size={16} />
                          </button>
                          <button
                            onClick={() =>
                              setDeleteTarget({
                                type: "invitation",
                                id: inv.id,
                                label: inv.email,
                              })
                            }
                            className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20"
                            title="Revoke invitation"
                          >
                            <X size={16} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Invite User Modal */}
      <Modal
        isOpen={showInviteModal}
        onClose={() => {
          setShowInviteModal(false);
          setFormError(null);
          setLastInviteUrl(null);
          setCopiedInviteUrl(false);
        }}
        title="Invite User"
        size="md"
      >
        {lastInviteUrl ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 dark:border-green-800 dark:bg-green-900/20">
              <p className="text-sm font-medium text-green-800 dark:text-green-300">
                Invitation sent successfully!
              </p>
              <p className="mt-1 text-xs text-green-600 dark:text-green-400">
                If SMTP is not configured, share this link with the user
                directly. The link expires in 7 days.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Invitation Link
              </label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={lastInviteUrl}
                  className="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-xs text-gray-600 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-300"
                />
                <button
                  onClick={() => handleCopyInviteUrl(lastInviteUrl)}
                  className="flex shrink-0 items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                  title="Copy link"
                >
                  {copiedInviteUrl ? (
                    <Check size={14} className="text-green-600" />
                  ) : (
                    <Copy size={14} />
                  )}
                </button>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                onClick={() => {
                  setLastInviteUrl(null);
                  setCopiedInviteUrl(false);
                }}
              >
                Invite Another
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleInviteUser} className="space-y-4">
            <div>
              <label
                htmlFor="inv_email"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Email
              </label>
              <input
                id="inv_email"
                type="email"
                required
                value={inviteForm.email}
                onChange={(e) =>
                  setInviteForm((p) => ({ ...p, email: e.target.value }))
                }
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                placeholder="user@company.com"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                An invitation link will be sent. The user will set their own
                name and password.
              </p>
            </div>
            <div>
              <label
                htmlFor="inv_role"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Role
              </label>
              <select
                id="inv_role"
                value={inviteForm.role}
                onChange={(e) =>
                  setInviteForm((p) => ({ ...p, role: e.target.value }))
                }
                className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
              >
                <optgroup label="System Roles">
                  <option value="viewer">Viewer</option>
                  <option value="admin">Administrator</option>
                </optgroup>
                {roles.filter((r) => !r.is_system).length > 0 && (
                  <optgroup label="Custom Roles">
                    {roles
                      .filter((r) => !r.is_system)
                      .map((r) => (
                        <option key={r.id} value={r.name}>
                          {r.name}
                        </option>
                      ))}
                  </optgroup>
                )}
              </select>
            </div>
            {formError && (
              <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                {formError}
              </div>
            )}
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowInviteModal(false);
                  setFormError(null);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" loading={isSubmitting}>
                Send Invitation
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* Delete/Revoke Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            if (deleteTarget.type === "user") {
              handleRemoveUser(deleteTarget.id);
            } else {
              handleRevokeInvitation(deleteTarget.id);
            }
            setDeleteTarget(null);
          }
        }}
        title={
          deleteTarget?.type === "user"
            ? "Remove Team Member"
            : "Revoke Invitation"
        }
        message={
          deleteTarget?.type === "user"
            ? `Remove "${deleteTarget?.label ?? ""}" from the team?`
            : `Revoke invitation for "${deleteTarget?.label ?? ""}"?`
        }
        confirmLabel={deleteTarget?.type === "user" ? "Remove" : "Revoke"}
      />
    </>
  );
}
