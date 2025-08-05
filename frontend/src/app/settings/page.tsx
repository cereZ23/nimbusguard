"use client";

import { useCallback, useRef, useState } from "react";
import Image from "next/image";
import useSWR from "swr";
import {
  Calendar,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  Download,
  FileText,
  Globe,
  Hash,
  Key,
  MessageSquare,
  Paintbrush,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Shield,
  Trash2,
  Upload,
  X,
  UserPlus,
  Users,
} from "lucide-react";
import AppShell from "@/components/layout/app-shell";
import BrandingSection from "@/components/settings/branding-section";
import ScimSection from "@/components/settings/scim-section";
import SsoSection from "@/components/settings/sso-section";
import ErrorState from "@/components/ui/error-state";
import api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import type {
  ApiKey,
  ApiKeyCreated,
  CloudAccount,
  CloudProvider,
  Invitation,
  InvitationCreated,
  JiraIntegration,
  JiraTestResult,
  MfaSetupResponse,
  PermissionListResponse,
  ReportHistoryEntry,
  Role,
  ScheduledReport,
  SlackIntegration,
  SlackTestResult,
  TenantBranding,
  TenantUser,
  Webhook,
  WebhookTestResult,
} from "@/types";

interface AddAccountForm {
  provider: CloudProvider;
  display_name: string;
  provider_account_id: string;
  tenant_id: string;
  client_id: string;
  client_secret: string;
}

const EMPTY_FORM: AddAccountForm = {
  provider: "azure",
  display_name: "",
  provider_account_id: "",
  tenant_id: "",
  client_id: "",
  client_secret: "",
};

export default function SettingsPage() {
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

  // -- SWR: accounts --
  const {
    data: accountsEnvelope,
    error: accountsError,
    isLoading: accountsLoading,
    mutate: mutateAccounts,
  } = useSWR("/accounts");

  // -- SWR: users --
  const {
    data: usersEnvelope,
    error: usersError,
    isLoading: usersLoading,
    mutate: mutateUsers,
  } = useSWR("/users");

  // -- SWR: webhooks --
  const {
    data: webhooksEnvelope,
    error: webhooksError,
    isLoading: webhooksLoading,
    mutate: mutateWebhooks,
  } = useSWR("/webhooks");

  // -- SWR: API keys --
  const {
    data: apiKeysEnvelope,
    error: apiKeysError,
    isLoading: apiKeysLoading,
    mutate: mutateApiKeys,
  } = useSWR("/api-keys");

  // -- SWR: scheduled reports --
  const {
    data: scheduledReportsEnvelope,
    error: scheduledReportsError,
    isLoading: scheduledReportsLoading,
    mutate: mutateScheduledReports,
  } = useSWR("/scheduled-reports");

  // -- SWR: slack integrations --
  const {
    data: slackEnvelope,
    error: slackError,
    isLoading: slackLoading,
    mutate: mutateSlack,
  } = useSWR("/integrations/slack");

  // -- SWR: Jira integrations --
  const {
    data: jiraEnvelope,
    error: jiraError,
    isLoading: jiraLoading,
    mutate: mutateJira,
  } = useSWR("/integrations/jira");

  // -- SWR: roles --
  const {
    data: rolesEnvelope,
    error: rolesError,
    isLoading: rolesLoading,
    mutate: mutateRoles,
  } = useSWR("/roles");

  // -- SWR: permissions catalog --
  const { data: permissionsEnvelope } = useSWR("/roles/permissions");

  // -- SWR: invitations --
  const { data: invitationsEnvelope, mutate: mutateInvitations } =
    useSWR("/invitations");

  // Unwrap API envelope data
  const accounts = (accountsEnvelope?.data ?? []) as CloudAccount[];
  const users = (usersEnvelope?.data ?? []) as TenantUser[];
  const webhooks = (webhooksEnvelope?.data ?? []) as Webhook[];
  const apiKeys = (apiKeysEnvelope?.data ?? []) as ApiKey[];
  const scheduledReports = (scheduledReportsEnvelope?.data ??
    []) as ScheduledReport[];
  const slackIntegrations = (slackEnvelope?.data ?? []) as SlackIntegration[];
  const jiraIntegrations = (jiraEnvelope?.data ?? []) as JiraIntegration[];
  const roles = (rolesEnvelope?.data ?? []) as Role[];
  const permissionsCatalog = permissionsEnvelope?.data as
    | PermissionListResponse
    | undefined;
  const invitations = (invitationsEnvelope?.data ?? []) as Invitation[];
  const pendingInvitations = invitations.filter(
    (inv) => inv.status === "pending",
  );

  // Combined loading / error state
  const isLoading =
    accountsLoading ||
    usersLoading ||
    webhooksLoading ||
    apiKeysLoading ||
    scheduledReportsLoading ||
    slackLoading ||
    jiraLoading ||
    rolesLoading;
  const error =
    accountsError?.message ??
    usersError?.message ??
    webhooksError?.message ??
    apiKeysError?.message ??
    scheduledReportsError?.message ??
    slackError?.message ??
    jiraError?.message ??
    rolesError?.message ??
    accountsEnvelope?.error ??
    usersEnvelope?.error ??
    webhooksEnvelope?.error ??
    apiKeysEnvelope?.error ??
    scheduledReportsEnvelope?.error ??
    slackEnvelope?.error ??
    jiraEnvelope?.error ??
    rolesEnvelope?.error ??
    null;

  const handleRetry = () => {
    mutateAccounts();
    mutateUsers();
    mutateWebhooks();
    mutateApiKeys();
    mutateScheduledReports();
    mutateSlack();
    mutateJira();
    mutateRoles();
  };

  const [actionError, setActionError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [form, setForm] = useState<AddAccountForm>(EMPTY_FORM);
  const [inviteForm, setInviteForm] = useState({
    email: "",
    role: "viewer",
  });
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);
  const [copiedInviteUrl, setCopiedInviteUrl] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Test connection state for Add Account modal
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [testConnectionResult, setTestConnectionResult] = useState<{
    success: boolean;
    resource_count: number;
    message: string;
  } | null>(null);

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setTestConnectionResult(null);
    try {
      const res = await api.post("/accounts/test-connection", {
        provider: form.provider,
        tenant_id: form.tenant_id,
        client_id: form.client_id,
        client_secret: form.client_secret,
        subscription_id: form.provider_account_id,
      });
      setTestConnectionResult(
        res.data.data as {
          success: boolean;
          resource_count: number;
          message: string;
        },
      );
    } catch {
      setTestConnectionResult({
        success: false,
        resource_count: 0,
        message: "Request failed. Please check your network connection.",
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const isTestConnectionReady =
    form.provider === "azure" &&
    form.provider_account_id.trim().length > 0 &&
    form.tenant_id.trim().length > 0 &&
    form.client_id.trim().length > 0 &&
    form.client_secret.trim().length > 0;

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);

    try {
      await api.post("/accounts", {
        provider: form.provider,
        display_name: form.display_name,
        provider_account_id: form.provider_account_id,
        credentials: {
          tenant_id: form.tenant_id,
          client_id: form.client_id,
          client_secret: form.client_secret,
        },
      });
      setShowAddModal(false);
      setForm(EMPTY_FORM);
      setTestConnectionResult(null);
      mutateAccounts();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      setFormError(
        axiosErr.response?.data?.error ??
          "Failed to add account. Check your credentials.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const [scanningId, setScanningId] = useState<string | null>(null);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const handleTriggerScan = async (accountId: string) => {
    setScanningId(accountId);
    setScanMessage(null);
    try {
      await api.post("/scans", { cloud_account_id: accountId });
      setScanMessage("Scan started successfully!");
      setTimeout(() => setScanMessage(null), 5000);
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { status?: number; data?: { detail?: string } };
      };
      if (axiosErr.response?.status === 429) {
        setScanMessage("Rate limit reached — try again later.");
      } else if (axiosErr.response?.status === 409) {
        setScanMessage("A scan is already running.");
      } else {
        setScanMessage(axiosErr.response?.data?.detail ?? "Scan failed.");
      }
      setTimeout(() => setScanMessage(null), 5000);
    } finally {
      setScanningId(null);
    }
  };

  const handleDeleteAccount = async (accountId: string, name: string) => {
    if (!window.confirm(`Remove "${name}"? Associated data will be deleted.`)) {
      return;
    }
    setActionError(null);
    try {
      await api.delete(`/accounts/${accountId}`);
      // Optimistic update: remove from local cache immediately, then revalidate
      mutateAccounts(
        (current: typeof accountsEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as CloudAccount[]).filter(
              (a) => a.id !== accountId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      setActionError(
        axiosErr.response?.data?.error ?? "Failed to remove account.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

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

  const handleRevokeInvitation = async (
    invitationId: string,
    email: string,
  ) => {
    if (!window.confirm(`Revoke invitation for "${email}"?`)) return;
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

  const getUserRoleValue = (u: TenantUser): string => {
    if (u.role_id) return u.role_id;
    return u.role;
  };

  const getUserRoleDisplay = (u: TenantUser): string => {
    if (u.role_name) return u.role_name;
    if (u.role === "admin") return "Administrator";
    if (u.role === "viewer") return "Viewer";
    return u.role;
  };

  const handleRemoveUser = async (userId: string, email: string) => {
    if (!window.confirm(`Remove "${email}" from the team?`)) return;
    setActionError(null);
    try {
      await api.delete(`/users/${userId}`);
      // Optimistic update: remove from local cache immediately, then revalidate
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

  // -- Webhook state --
  const ALLOWED_EVENTS = [
    "scan.completed",
    "scan.failed",
    "finding.high",
    "finding.critical_change",
  ];
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  const [webhookForm, setWebhookForm] = useState({
    url: "",
    secret: "",
    events: [] as string[],
    description: "",
  });
  const [testingWebhookId, setTestingWebhookId] = useState<string | null>(null);
  const [webhookTestResult, setWebhookTestResult] =
    useState<WebhookTestResult | null>(null);

  const handleAddWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/webhooks", {
        url: webhookForm.url,
        secret: webhookForm.secret || undefined,
        events: webhookForm.events,
        description: webhookForm.description || undefined,
      });
      setShowWebhookModal(false);
      setWebhookForm({ url: "", secret: "", events: [], description: "" });
      mutateWebhooks();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create webhook.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteWebhook = async (webhookId: string, url: string) => {
    if (!window.confirm(`Remove webhook "${url}"?`)) return;
    setActionError(null);
    try {
      await api.delete(`/webhooks/${webhookId}`);
      mutateWebhooks(
        (current: typeof webhooksEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as Webhook[]).filter((w) => w.id !== webhookId),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete webhook.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleWebhook = async (
    webhookId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/webhooks/${webhookId}`, {
        is_active: !currentActive,
      });
      mutateWebhooks();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle webhook.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestWebhook = async (webhookId: string) => {
    setTestingWebhookId(webhookId);
    setWebhookTestResult(null);
    try {
      const res = await api.post(`/webhooks/${webhookId}/test`);
      setWebhookTestResult(res.data.data as WebhookTestResult);
      mutateWebhooks();
      setTimeout(() => {
        setWebhookTestResult(null);
        setTestingWebhookId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setWebhookTestResult({
        status_code: 0,
        response_body: axiosErr.response?.data?.detail ?? "Test failed",
        success: false,
      });
      setTimeout(() => {
        setWebhookTestResult(null);
        setTestingWebhookId(null);
      }, 5000);
    }
  };

  const toggleWebhookEvent = (event: string) => {
    setWebhookForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  // -- Slack integration state --
  const SLACK_EVENTS = [
    "scan.completed",
    "scan.failed",
    "finding.high",
    "finding.critical_change",
  ];
  const [showSlackModal, setShowSlackModal] = useState(false);
  const [slackForm, setSlackForm] = useState({
    webhook_url: "",
    channel_name: "",
    events: [] as string[],
  });
  const [testingSlackId, setTestingSlackId] = useState<string | null>(null);
  const [slackTestResult, setSlackTestResult] =
    useState<SlackTestResult | null>(null);

  const handleAddSlack = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/integrations/slack", {
        webhook_url: slackForm.webhook_url,
        channel_name: slackForm.channel_name || undefined,
        events: slackForm.events,
      });
      setShowSlackModal(false);
      setSlackForm({ webhook_url: "", channel_name: "", events: [] });
      mutateSlack();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ??
          "Failed to create Slack integration.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteSlack = async (integrationId: string, name: string) => {
    if (!window.confirm(`Remove Slack integration "${name}"?`)) return;
    setActionError(null);
    try {
      await api.delete(`/integrations/slack/${integrationId}`);
      mutateSlack(
        (current: typeof slackEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as SlackIntegration[]).filter(
              (s) => s.id !== integrationId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ??
          "Failed to delete Slack integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleSlack = async (
    integrationId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/integrations/slack/${integrationId}`, {
        is_active: !currentActive,
      });
      mutateSlack();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ??
          "Failed to toggle Slack integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestSlack = async (integrationId: string) => {
    setTestingSlackId(integrationId);
    setSlackTestResult(null);
    try {
      const res = await api.post(`/integrations/slack/${integrationId}/test`);
      setSlackTestResult(res.data.data as SlackTestResult);
      setTimeout(() => {
        setSlackTestResult(null);
        setTestingSlackId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSlackTestResult({
        success: false,
        response_body: axiosErr.response?.data?.detail ?? "Test failed",
      });
      setTimeout(() => {
        setSlackTestResult(null);
        setTestingSlackId(null);
      }, 5000);
    }
  };

  const toggleSlackEvent = (event: string) => {
    setSlackForm((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  // -- Jira integration state --
  const JIRA_ISSUE_TYPES = ["Bug", "Task", "Story", "Epic", "Sub-task"];
  const [showJiraModal, setShowJiraModal] = useState(false);
  const [jiraForm, setJiraForm] = useState({
    base_url: "",
    email: "",
    api_token: "",
    project_key: "",
    issue_type: "Bug",
  });
  const [testingJiraId, setTestingJiraId] = useState<string | null>(null);
  const [jiraTestResult, setJiraTestResult] = useState<JiraTestResult | null>(
    null,
  );

  const handleAddJira = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.post("/integrations/jira", {
        base_url: jiraForm.base_url,
        email: jiraForm.email,
        api_token: jiraForm.api_token,
        project_key: jiraForm.project_key,
        issue_type: jiraForm.issue_type,
      });
      setShowJiraModal(false);
      setJiraForm({
        base_url: "",
        email: "",
        api_token: "",
        project_key: "",
        issue_type: "Bug",
      });
      mutateJira();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create Jira integration.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteJira = async (integrationId: string, baseUrl: string) => {
    if (!window.confirm(`Remove Jira integration "${baseUrl}"?`)) return;
    setActionError(null);
    try {
      await api.delete(`/integrations/jira/${integrationId}`);
      mutateJira(
        (current: typeof jiraEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as JiraIntegration[]).filter(
              (j) => j.id !== integrationId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete Jira integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleJira = async (
    integrationId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/integrations/jira/${integrationId}`, {
        is_active: !currentActive,
      });
      mutateJira();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle Jira integration.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleTestJira = async (integrationId: string) => {
    setTestingJiraId(integrationId);
    setJiraTestResult(null);
    try {
      const res = await api.post(`/integrations/jira/${integrationId}/test`);
      setJiraTestResult(res.data.data as JiraTestResult);
      setTimeout(() => {
        setJiraTestResult(null);
        setTestingJiraId(null);
      }, 5000);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setJiraTestResult({
        success: false,
        message: axiosErr.response?.data?.detail ?? "Test failed",
      });
      setTimeout(() => {
        setJiraTestResult(null);
        setTestingJiraId(null);
      }, 5000);
    }
  };

  // -- API Keys state --
  const ALLOWED_SCOPES = ["read", "write", "scan"];
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [apiKeyForm, setApiKeyForm] = useState({
    name: "",
    scopes: ["read"] as string[],
    expires_in_days: "" as string,
  });
  const [createdApiKey, setCreatedApiKey] = useState<ApiKeyCreated | null>(
    null,
  );
  const [copiedKey, setCopiedKey] = useState(false);

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      const payload: {
        name: string;
        scopes: string[];
        expires_in_days?: number;
      } = {
        name: apiKeyForm.name,
        scopes: apiKeyForm.scopes,
      };
      if (apiKeyForm.expires_in_days) {
        payload.expires_in_days = parseInt(apiKeyForm.expires_in_days, 10);
      }
      const res = await api.post("/api-keys", payload);
      setCreatedApiKey(res.data.data as ApiKeyCreated);
      setApiKeyForm({ name: "", scopes: ["read"], expires_in_days: "" });
      mutateApiKeys();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create API key.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteApiKey = async (keyId: string, keyName: string) => {
    if (!window.confirm(`Revoke API key "${keyName}"? This cannot be undone.`))
      return;
    setActionError(null);
    try {
      await api.delete(`/api-keys/${keyId}`);
      mutateApiKeys(
        (current: typeof apiKeysEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as ApiKey[]).filter((k) => k.id !== keyId),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to revoke API key.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleCopyApiKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const toggleApiKeyScope = (scope: string) => {
    setApiKeyForm((prev) => ({
      ...prev,
      scopes: prev.scopes.includes(scope)
        ? prev.scopes.filter((s) => s !== scope)
        : [...prev.scopes, scope],
    }));
  };

  const isActive = (account: CloudAccount) => account.status === "active";

  const updateField = (field: keyof AddAccountForm, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  // -- SIEM Export state --
  const [siemDownloading, setSiemDownloading] = useState<string | null>(null);
  const [siemError, setSiemError] = useState<string | null>(null);
  const [siemSeverity, setSiemSeverity] = useState("");
  const [siemStatus, setSiemStatus] = useState("");

  const handleSiemExport = async (format: "cef" | "leef" | "jsonl") => {
    setSiemDownloading(format);
    setSiemError(null);
    try {
      const params = new URLSearchParams();
      if (siemSeverity) params.set("severity", siemSeverity);
      if (siemStatus) params.set("status", siemStatus);
      const queryString = params.toString() ? `?${params.toString()}` : "";
      const response = await api.get(`/export/siem/${format}${queryString}`, {
        responseType: "blob",
      });
      const ext = format === "jsonl" ? "jsonl" : format;
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `findings-export.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSiemError(
        axiosErr.response?.data?.detail ?? "Failed to export SIEM data.",
      );
      setTimeout(() => setSiemError(null), 5000);
    } finally {
      setSiemDownloading(null);
    }
  };

  // -- Report generation state --
  const [reportDownloading, setReportDownloading] = useState<string | null>(
    null,
  );
  const [reportError, setReportError] = useState<string | null>(null);
  const [complianceFramework, setComplianceFramework] = useState("cis_azure");

  const handleDownloadReport = async (
    endpoint: string,
    filename: string,
    params?: Record<string, string>,
  ) => {
    setReportDownloading(endpoint);
    setReportError(null);
    try {
      const queryString = params
        ? "?" + new URLSearchParams(params).toString()
        : "";
      const response = await api.get(`/reports/${endpoint}${queryString}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setReportError(
        axiosErr.response?.data?.detail ?? "Failed to generate report.",
      );
      setTimeout(() => setReportError(null), 5000);
    } finally {
      setReportDownloading(null);
    }
  };

  // -- Scheduled Reports state --
  const REPORT_TYPE_LABELS: Record<string, string> = {
    executive_summary: "Executive Summary",
    compliance: "Compliance",
    technical_detail: "Technical Detail",
  };
  const SCHEDULE_LABELS: Record<string, string> = {
    daily: "Daily",
    weekly: "Weekly",
    monthly: "Monthly",
  };

  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    name: "",
    report_type: "executive_summary",
    schedule: "weekly",
    config_framework: "cis_azure",
    config_severity: "",
  });
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [reportHistory, setReportHistory] = useState<
    Record<string, ReportHistoryEntry[]>
  >({});
  const [historyLoading, setHistoryLoading] = useState<string | null>(null);

  const handleCreateScheduledReport = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    try {
      const config: Record<string, string> = {};
      if (scheduleForm.report_type === "compliance") {
        config.framework = scheduleForm.config_framework;
      }
      if (
        scheduleForm.report_type === "technical_detail" &&
        scheduleForm.config_severity
      ) {
        config.severity = scheduleForm.config_severity;
      }
      await api.post("/scheduled-reports", {
        name: scheduleForm.name,
        report_type: scheduleForm.report_type,
        schedule: scheduleForm.schedule,
        config,
      });
      setShowScheduleModal(false);
      setScheduleForm({
        name: "",
        report_type: "executive_summary",
        schedule: "weekly",
        config_framework: "cis_azure",
        config_severity: "",
      });
      mutateScheduledReports();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setFormError(
        axiosErr.response?.data?.detail ?? "Failed to create scheduled report.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleScheduledReport = async (
    reportId: string,
    currentActive: boolean,
  ) => {
    setActionError(null);
    try {
      await api.put(`/scheduled-reports/${reportId}`, {
        is_active: !currentActive,
      });
      mutateScheduledReports();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to toggle scheduled report.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleDeleteScheduledReport = async (
    reportId: string,
    name: string,
  ) => {
    if (!window.confirm(`Delete scheduled report "${name}"?`)) return;
    setActionError(null);
    try {
      await api.delete(`/scheduled-reports/${reportId}`);
      mutateScheduledReports(
        (current: typeof scheduledReportsEnvelope) => {
          if (!current?.data) return current;
          return {
            ...current,
            data: (current.data as ScheduledReport[]).filter(
              (r) => r.id !== reportId,
            ),
          };
        },
        { revalidate: true },
      );
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setActionError(
        axiosErr.response?.data?.detail ?? "Failed to delete scheduled report.",
      );
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const handleToggleHistory = async (reportId: string) => {
    if (expandedReport === reportId) {
      setExpandedReport(null);
      return;
    }
    setExpandedReport(reportId);
    if (!reportHistory[reportId]) {
      setHistoryLoading(reportId);
      try {
        const res = await api.get(
          `/scheduled-reports/${reportId}/history?size=10`,
        );
        setReportHistory((prev) => ({
          ...prev,
          [reportId]: (res.data.data ?? []) as ReportHistoryEntry[],
        }));
      } catch {
        setReportHistory((prev) => ({
          ...prev,
          [reportId]: [],
        }));
      } finally {
        setHistoryLoading(null);
      }
    }
  };

  const handleDownloadHistoryReport = async (historyId: string) => {
    try {
      const response = await api.get(
        `/scheduled-reports/history/${historyId}/download`,
        { responseType: "blob" },
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `report-${historyId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setActionError("Failed to download report.");
      setTimeout(() => setActionError(null), 5000);
    }
  };

  const formatFileSize = (bytes: number | null): string => {
    if (bytes === null || bytes === undefined) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Settings
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Manage connected cloud accounts and scan configurations
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            <Plus size={16} />
            Add Account
          </button>
        </div>

        {/* Error state for initial load */}
        {error && <ErrorState message={error} onRetry={handleRetry} />}

        {/* Action error banner */}
        {actionError && (
          <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {actionError}
          </div>
        )}

        {/* Cloud Accounts */}
        {!error && (
          <>
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Cloud Accounts
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Connected cloud provider subscriptions and accounts
                </p>
              </div>

              {isLoading ? (
                <div className="flex h-48 items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {accounts.map((account) => (
                    <div
                      key={account.id}
                      className="flex items-center justify-between px-6 py-4"
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            isActive(account) ? "bg-green-400" : "bg-gray-300"
                          }`}
                          title={account.status}
                        />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {account.display_name}
                          </p>
                          <div className="mt-1 flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                              {account.provider.toUpperCase()}
                            </span>
                            <span className="font-mono text-xs">
                              {account.provider_account_id}
                            </span>
                            {account.last_scan_at && (
                              <span>
                                Last scan:{" "}
                                {new Date(
                                  account.last_scan_at,
                                ).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {scanMessage && scanningId === null && (
                          <span className="text-xs text-gray-600 dark:text-gray-300">
                            {scanMessage}
                          </span>
                        )}
                        <button
                          onClick={() => handleTriggerScan(account.id)}
                          disabled={
                            !isActive(account) || scanningId === account.id
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                          title="Trigger scan"
                        >
                          <RefreshCw
                            size={14}
                            className={
                              scanningId === account.id ? "animate-spin" : ""
                            }
                          />
                          {scanningId === account.id ? "Scanning..." : "Scan"}
                        </button>
                        <button
                          onClick={() =>
                            handleDeleteAccount(
                              account.id,
                              account.display_name,
                            )
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                          title="Remove account"
                        >
                          <Trash2 size={14} />
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}

                  {accounts.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                      <p className="text-sm">
                        No cloud accounts connected yet.
                      </p>
                      <p className="mt-1 text-sm">
                        Click &quot;Add Account&quot; to get started.
                      </p>
                    </div>
                  )}
                </div>
              )}
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

            {/* Scan Configuration */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Scan Configuration
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Configure automatic scan schedules for each account
                </p>
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {accounts.map((account) => (
                  <ScanScheduleRow
                    key={account.id}
                    account={account}
                    onUpdated={() => mutateAccounts()}
                  />
                ))}
                {accounts.length === 0 && (
                  <div className="flex items-center justify-center py-8 text-sm text-gray-500 dark:text-gray-400">
                    Add a cloud account to configure scan schedules.
                  </div>
                )}
              </div>
            </div>

            {/* Roles & Permissions */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Roles & Permissions
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Define custom roles with granular permissions
                  </p>
                </div>
                <button
                  onClick={handleOpenCreateRole}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Create Role
                </button>
              </div>

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
            </div>

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
                        These codes can be used to access your account if you
                        lose your authenticator device. Each code can only be
                        used once.
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
                        {copiedBackupCodes ? (
                          <Check size={14} />
                        ) : (
                          <Copy size={14} />
                        )}
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
                        <button
                          type="submit"
                          disabled={
                            mfaLoading || mfaVerifyCode.trim().length !== 6
                          }
                          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {mfaLoading ? (
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                          ) : (
                            <Check size={14} />
                          )}
                          Verify and enable
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowMfaSetup(false);
                            setMfaSetupData(null);
                            setMfaVerifyCode("");
                            setMfaError(null);
                          }}
                          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  </div>
                )}
                {showMfaDisable && (
                  <div className="mb-4">
                    <form onSubmit={handleMfaDisable} className="space-y-3">
                      <p className="text-sm text-gray-600 dark:text-gray-300">
                        Enter your password to disable two-factor
                        authentication:
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
                        <button
                          type="submit"
                          disabled={mfaLoading || !mfaDisablePassword}
                          className="flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {mfaLoading ? (
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                          ) : (
                            <X size={14} />
                          )}
                          Disable 2FA
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowMfaDisable(false);
                            setMfaDisablePassword("");
                            setMfaError(null);
                          }}
                          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
                        >
                          Cancel
                        </button>
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
                      <button
                        onClick={handleMfaSetup}
                        disabled={mfaLoading}
                        className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {mfaLoading ? (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                        ) : (
                          <Shield size={14} />
                        )}
                        Enable 2FA
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Team Management */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Team Members
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Manage users and roles for your tenant
                  </p>
                </div>
                <button
                  onClick={() => setShowInviteModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <UserPlus size={16} />
                  Invite User
                </button>
              </div>

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
                        onClick={() => handleRemoveUser(u.id, u.email)}
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
                              handleRevokeInvitation(inv.id, inv.email)
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
            </div>

            {/* Webhooks */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Webhooks
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Receive HTTP notifications when events occur
                  </p>
                </div>
                <button
                  onClick={() => setShowWebhookModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Webhook
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {webhooks.map((wh) => (
                  <div
                    key={wh.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          wh.is_active ? "bg-green-400" : "bg-gray-300"
                        }`}
                        title={wh.is_active ? "Active" : "Inactive"}
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {wh.description || wh.url}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                          <Globe size={12} />
                          <span className="max-w-xs truncate font-mono text-xs">
                            {wh.url}
                          </span>
                          {wh.events.map((ev) => (
                            <span
                              key={ev}
                              className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                            >
                              {ev}
                            </span>
                          ))}
                          {wh.last_triggered_at && (
                            <span className="text-xs">
                              Last:{" "}
                              {new Date(wh.last_triggered_at).toLocaleString()}
                              {wh.last_status_code !== null && (
                                <span
                                  className={`ml-1 ${
                                    wh.last_status_code >= 200 &&
                                    wh.last_status_code < 300
                                      ? "text-green-600"
                                      : "text-red-600"
                                  }`}
                                >
                                  ({wh.last_status_code})
                                </span>
                              )}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {testingWebhookId === wh.id && webhookTestResult && (
                        <span
                          className={`text-xs ${
                            webhookTestResult.success
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {webhookTestResult.success
                            ? "OK"
                            : `Failed (${webhookTestResult.status_code})`}
                        </span>
                      )}
                      <button
                        onClick={() => handleTestWebhook(wh.id)}
                        disabled={testingWebhookId === wh.id}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                        title="Send test payload"
                      >
                        <Send size={14} />
                        Test
                      </button>
                      <button
                        onClick={() => handleToggleWebhook(wh.id, wh.is_active)}
                        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                          wh.is_active
                            ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                            : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                        }`}
                        title={
                          wh.is_active ? "Disable webhook" : "Enable webhook"
                        }
                      >
                        <Check size={14} />
                        {wh.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => handleDeleteWebhook(wh.id, wh.url)}
                        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                        title="Remove webhook"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
                {webhooks.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <Globe size={20} className="mb-2" />
                    <p className="text-sm">No webhooks configured.</p>
                    <p className="mt-1 text-sm">
                      Add a webhook to receive event notifications.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Slack Integration */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Slack Integration
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Send security notifications to Slack channels
                  </p>
                </div>
                <button
                  onClick={() => setShowSlackModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Slack Integration
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {slackIntegrations.map((si) => (
                  <div
                    key={si.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          si.is_active ? "bg-green-400" : "bg-gray-300"
                        }`}
                        title={si.is_active ? "Active" : "Inactive"}
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {si.channel_name || "Slack Webhook"}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                          <MessageSquare size={12} />
                          <span className="max-w-xs truncate font-mono text-xs">
                            {si.webhook_url.replace(
                              /^(https:\/\/hooks\.slack\.com\/services\/T[^/]+\/).*/,
                              "$1...",
                            )}
                          </span>
                          {si.events.map((ev) => (
                            <span
                              key={ev}
                              className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                            >
                              {ev}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {testingSlackId === si.id && slackTestResult && (
                        <span
                          className={`text-xs ${
                            slackTestResult.success
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {slackTestResult.success ? "OK" : "Failed"}
                        </span>
                      )}
                      <button
                        onClick={() => handleTestSlack(si.id)}
                        disabled={testingSlackId === si.id}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                        title="Send test message"
                      >
                        <Send size={14} />
                        Test
                      </button>
                      <button
                        onClick={() => handleToggleSlack(si.id, si.is_active)}
                        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                          si.is_active
                            ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                            : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                        }`}
                        title={si.is_active ? "Disable" : "Enable"}
                      >
                        <Check size={14} />
                        {si.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() =>
                          handleDeleteSlack(
                            si.id,
                            si.channel_name || "Slack Webhook",
                          )
                        }
                        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                        title="Remove Slack integration"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
                {slackIntegrations.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <MessageSquare size={20} className="mb-2" />
                    <p className="text-sm">No Slack integrations configured.</p>
                    <p className="mt-1 text-sm">
                      Add a Slack integration to receive security notifications.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Jira Integration */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Jira Integration
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Create Jira tickets from security findings
                  </p>
                </div>
                <button
                  onClick={() => setShowJiraModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Jira Integration
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {jiraIntegrations.map((ji) => (
                  <div
                    key={ji.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className={`h-3 w-3 rounded-full ${
                          ji.is_active ? "bg-green-400" : "bg-gray-300"
                        }`}
                        title={ji.is_active ? "Active" : "Inactive"}
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {ji.project_key} ({ji.issue_type})
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                          <Globe size={12} />
                          <span className="max-w-xs truncate font-mono text-xs">
                            {ji.base_url}
                          </span>
                          <span className="text-xs">{ji.email}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {testingJiraId === ji.id && jiraTestResult && (
                        <span
                          className={`text-xs ${
                            jiraTestResult.success
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {jiraTestResult.success
                            ? jiraTestResult.message
                            : jiraTestResult.message}
                        </span>
                      )}
                      <button
                        onClick={() => handleTestJira(ji.id)}
                        disabled={testingJiraId === ji.id}
                        className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                        title="Test Jira connection"
                      >
                        <Send size={14} />
                        Test
                      </button>
                      <button
                        onClick={() => handleToggleJira(ji.id, ji.is_active)}
                        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                          ji.is_active
                            ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                            : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                        }`}
                        title={ji.is_active ? "Disable" : "Enable"}
                      >
                        <Check size={14} />
                        {ji.is_active ? "Disable" : "Enable"}
                      </button>
                      <button
                        onClick={() => handleDeleteJira(ji.id, ji.base_url)}
                        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                        title="Remove Jira integration"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
                {jiraIntegrations.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <Globe size={20} className="mb-2" />
                    <p className="text-sm">No Jira integrations configured.</p>
                    <p className="mt-1 text-sm">
                      Add a Jira integration to create tickets from findings.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* API Keys */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    API Keys
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Manage API keys for CI/CD and programmatic access
                  </p>
                </div>
                <button
                  onClick={() => setShowApiKeyModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Create API Key
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {apiKeys.map((ak) => (
                  <div
                    key={ak.id}
                    className="flex items-center justify-between px-6 py-4"
                  >
                    <div className="flex items-center gap-4">
                      <Key
                        size={16}
                        className="text-gray-400 dark:text-gray-500"
                      />
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {ak.name}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                          <span className="font-mono text-xs">
                            {ak.key_prefix}...
                          </span>
                          {ak.scopes.map((scope) => (
                            <span
                              key={scope}
                              className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                            >
                              {scope}
                            </span>
                          ))}
                          <span className="text-xs">
                            Created:{" "}
                            {new Date(ak.created_at).toLocaleDateString()}
                          </span>
                          {ak.last_used_at && (
                            <span className="text-xs">
                              Last used:{" "}
                              {new Date(ak.last_used_at).toLocaleString()}
                            </span>
                          )}
                          {ak.expires_at && (
                            <span
                              className={`text-xs ${
                                new Date(ak.expires_at) < new Date()
                                  ? "text-red-600 dark:text-red-400"
                                  : "text-gray-500 dark:text-gray-400"
                              }`}
                            >
                              {new Date(ak.expires_at) < new Date()
                                ? "Expired"
                                : `Expires: ${new Date(ak.expires_at).toLocaleDateString()}`}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDeleteApiKey(ak.id, ak.name)}
                        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                        title="Revoke API key"
                      >
                        <Trash2 size={14} />
                        Revoke
                      </button>
                    </div>
                  </div>
                ))}
                {apiKeys.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <Key size={20} className="mb-2" />
                    <p className="text-sm">No API keys created.</p>
                    <p className="mt-1 text-sm">
                      Create an API key for CI/CD integrations.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Reports */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Reports
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Generate and download PDF reports for your security posture
                </p>
              </div>

              <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-700">
                {reportError && (
                  <div className="bg-red-50 px-6 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                    {reportError}
                  </div>
                )}

                {/* Executive Summary */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <FileText
                      size={16}
                      className="text-blue-500 dark:text-blue-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Executive Summary
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        High-level security posture overview with KPIs and top
                        failing controls
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      handleDownloadReport(
                        "executive-summary",
                        "executive-summary.pdf",
                      )
                    }
                    disabled={reportDownloading === "executive-summary"}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    <Download
                      size={14}
                      className={
                        reportDownloading === "executive-summary"
                          ? "animate-pulse"
                          : ""
                      }
                    />
                    {reportDownloading === "executive-summary"
                      ? "Generating..."
                      : "Download PDF"}
                  </button>
                </div>

                {/* Compliance Report */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <FileText
                      size={16}
                      className="text-green-500 dark:text-green-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Compliance Report
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Framework compliance status with control-level detail
                        and remediation
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={complianceFramework}
                      onChange={(e) => setComplianceFramework(e.target.value)}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
                    >
                      <option value="cis_azure">CIS Azure</option>
                      <option value="soc2">SOC 2</option>
                      <option value="nist">NIST CSF</option>
                      <option value="iso27001">ISO 27001</option>
                    </select>
                    <button
                      onClick={() =>
                        handleDownloadReport(
                          "compliance",
                          `compliance-${complianceFramework}.pdf`,
                          { framework: complianceFramework },
                        )
                      }
                      disabled={reportDownloading === "compliance"}
                      className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                    >
                      <Download
                        size={14}
                        className={
                          reportDownloading === "compliance"
                            ? "animate-pulse"
                            : ""
                        }
                      />
                      {reportDownloading === "compliance"
                        ? "Generating..."
                        : "Download PDF"}
                    </button>
                  </div>
                </div>

                {/* Technical Detail */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <FileText
                      size={16}
                      className="text-orange-500 dark:text-orange-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Technical Detail
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Detailed findings with evidence, asset inventory, and
                        remediation guidance
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      handleDownloadReport(
                        "technical-detail",
                        "technical-detail.pdf",
                      )
                    }
                    disabled={reportDownloading === "technical-detail"}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    <Download
                      size={14}
                      className={
                        reportDownloading === "technical-detail"
                          ? "animate-pulse"
                          : ""
                      }
                    />
                    {reportDownloading === "technical-detail"
                      ? "Generating..."
                      : "Download PDF"}
                  </button>
                </div>
              </div>
            </div>

            {/* Scheduled Reports */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Scheduled Reports
                  </h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Configure recurring PDF reports generated automatically
                  </p>
                </div>
                <button
                  onClick={() => setShowScheduleModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  <Plus size={16} />
                  Add Schedule
                </button>
              </div>

              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {scheduledReports.map((sr) => (
                  <div key={sr.id}>
                    <div className="flex items-center justify-between px-6 py-4">
                      <div className="flex items-center gap-4">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            sr.is_active ? "bg-green-400" : "bg-gray-300"
                          }`}
                          title={sr.is_active ? "Active" : "Inactive"}
                        />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-gray-100">
                            {sr.name}
                          </p>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                              {REPORT_TYPE_LABELS[sr.report_type] ??
                                sr.report_type}
                            </span>
                            <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                              <Clock size={10} />
                              {SCHEDULE_LABELS[sr.schedule] ?? sr.schedule}
                            </span>
                            {sr.config && Object.keys(sr.config).length > 0 && (
                              <span className="text-xs text-gray-400">
                                {Object.entries(sr.config)
                                  .map(([k, v]) => `${k}: ${v}`)
                                  .join(", ")}
                              </span>
                            )}
                            {sr.last_run_at && (
                              <span className="text-xs">
                                Last:{" "}
                                {new Date(sr.last_run_at).toLocaleString()}
                              </span>
                            )}
                            {sr.next_run_at && sr.is_active && (
                              <span className="text-xs">
                                Next:{" "}
                                {new Date(sr.next_run_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleToggleHistory(sr.id)}
                          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                          title="View history"
                        >
                          {expandedReport === sr.id ? (
                            <ChevronUp size={14} />
                          ) : (
                            <ChevronDown size={14} />
                          )}
                          History
                        </button>
                        <button
                          onClick={() =>
                            handleToggleScheduledReport(sr.id, sr.is_active)
                          }
                          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                            sr.is_active
                              ? "border-yellow-300 bg-white text-yellow-700 hover:bg-yellow-50 dark:border-yellow-600 dark:bg-gray-700 dark:text-yellow-400"
                              : "border-green-300 bg-white text-green-700 hover:bg-green-50 dark:border-green-600 dark:bg-gray-700 dark:text-green-400"
                          }`}
                          title={sr.is_active ? "Pause" : "Activate"}
                        >
                          <Check size={14} />
                          {sr.is_active ? "Pause" : "Activate"}
                        </button>
                        <button
                          onClick={() =>
                            handleDeleteScheduledReport(sr.id, sr.name)
                          }
                          className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
                          title="Delete scheduled report"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {/* History panel */}
                    {expandedReport === sr.id && (
                      <div className="border-t border-gray-100 bg-gray-50 px-6 py-3 dark:border-gray-700 dark:bg-gray-900/50">
                        {historyLoading === sr.id ? (
                          <div className="flex items-center justify-center py-4">
                            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                          </div>
                        ) : (reportHistory[sr.id] ?? []).length === 0 ? (
                          <p className="py-3 text-center text-sm text-gray-500 dark:text-gray-400">
                            No reports generated yet.
                          </p>
                        ) : (
                          <div className="space-y-2">
                            <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
                              Recent Reports
                            </p>
                            {(reportHistory[sr.id] ?? []).map((entry) => (
                              <div
                                key={entry.id}
                                className="flex items-center justify-between rounded-lg bg-white px-4 py-2 dark:bg-gray-800"
                              >
                                <div className="flex items-center gap-3">
                                  <span
                                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                      entry.status === "completed"
                                        ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                        : "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                    }`}
                                  >
                                    {entry.status === "completed"
                                      ? "Completed"
                                      : "Failed"}
                                  </span>
                                  <span className="text-xs text-gray-500 dark:text-gray-400">
                                    {new Date(
                                      entry.generated_at,
                                    ).toLocaleString()}
                                  </span>
                                  {entry.file_size !== null && (
                                    <span className="text-xs text-gray-400">
                                      {formatFileSize(entry.file_size)}
                                    </span>
                                  )}
                                  {entry.error_message && (
                                    <span className="max-w-xs truncate text-xs text-red-500">
                                      {entry.error_message}
                                    </span>
                                  )}
                                </div>
                                {entry.status === "completed" && (
                                  <button
                                    onClick={() =>
                                      handleDownloadHistoryReport(entry.id)
                                    }
                                    className="flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                                  >
                                    <Download size={12} />
                                    Download
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {scheduledReports.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <Calendar size={20} className="mb-2" />
                    <p className="text-sm">No scheduled reports configured.</p>
                    <p className="mt-1 text-sm">
                      Add a schedule to automate report generation.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* SIEM Export */}
            <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
              <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  SIEM Export
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Export findings in SIEM-compatible formats for integration
                  with your security operations platform
                </p>
              </div>

              <div className="space-y-0 divide-y divide-gray-100 dark:divide-gray-700">
                {siemError && (
                  <div className="bg-red-50 px-6 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                    {siemError}
                  </div>
                )}

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-4 px-6 py-4">
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor="siem_severity"
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      Severity
                    </label>
                    <select
                      id="siem_severity"
                      value={siemSeverity}
                      onChange={(e) => setSiemSeverity(e.target.value)}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
                    >
                      <option value="">All severities</option>
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <label
                      htmlFor="siem_status"
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      Status
                    </label>
                    <select
                      id="siem_status"
                      value={siemStatus}
                      onChange={(e) => setSiemStatus(e.target.value)}
                      className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
                    >
                      <option value="">All statuses</option>
                      <option value="fail">Fail</option>
                      <option value="pass">Pass</option>
                      <option value="error">Error</option>
                    </select>
                  </div>
                </div>

                {/* CEF Format */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <Send
                      size={16}
                      className="text-purple-500 dark:text-purple-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        CEF Format
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Common Event Format -- Splunk, ArcSight, Microsoft
                        Sentinel, most SIEMs
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleSiemExport("cef")}
                    disabled={siemDownloading === "cef"}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    <Download
                      size={14}
                      className={
                        siemDownloading === "cef" ? "animate-pulse" : ""
                      }
                    />
                    {siemDownloading === "cef" ? "Exporting..." : "Download"}
                  </button>
                </div>

                {/* LEEF Format */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <Send
                      size={16}
                      className="text-orange-500 dark:text-orange-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        LEEF Format
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Log Event Extended Format -- IBM QRadar
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleSiemExport("leef")}
                    disabled={siemDownloading === "leef"}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    <Download
                      size={14}
                      className={
                        siemDownloading === "leef" ? "animate-pulse" : ""
                      }
                    />
                    {siemDownloading === "leef" ? "Exporting..." : "Download"}
                  </button>
                </div>

                {/* JSON Lines Format */}
                <div className="flex items-center justify-between px-6 py-4">
                  <div className="flex items-center gap-3">
                    <Send
                      size={16}
                      className="text-green-500 dark:text-green-400"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        JSON Lines
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Newline-delimited JSON -- Splunk HEC, Microsoft
                        Sentinel, Elastic
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleSiemExport("jsonl")}
                    disabled={siemDownloading === "jsonl"}
                    className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    <Download
                      size={14}
                      className={
                        siemDownloading === "jsonl" ? "animate-pulse" : ""
                      }
                    />
                    {siemDownloading === "jsonl" ? "Exporting..." : "Download"}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

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

      {/* Invite User Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Invite User
              </h2>
              <button
                onClick={() => {
                  setShowInviteModal(false);
                  setFormError(null);
                  setLastInviteUrl(null);
                  setCopiedInviteUrl(false);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

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
                  <button
                    onClick={() => {
                      setLastInviteUrl(null);
                      setCopiedInviteUrl(false);
                    }}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                  >
                    Invite Another
                  </button>
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
                  <button
                    type="button"
                    onClick={() => {
                      setShowInviteModal(false);
                      setFormError(null);
                    }}
                    className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isSubmitting ? "Sending..." : "Send Invitation"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Add Account Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Cloud Account
              </h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setForm(EMPTY_FORM);
                  setFormError(null);
                  setTestConnectionResult(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleAddAccount} className="space-y-4">
              {/* Provider */}
              <div>
                <label
                  htmlFor="provider"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Cloud Provider
                </label>
                <select
                  id="provider"
                  value={form.provider}
                  onChange={(e) => updateField("provider", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="azure">Azure</option>
                  <option value="aws">AWS</option>
                </select>
              </div>

              {/* Display Name */}
              <div>
                <label
                  htmlFor="display_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Display Name
                </label>
                <input
                  id="display_name"
                  type="text"
                  required
                  value={form.display_name}
                  onChange={(e) => updateField("display_name", e.target.value)}
                  placeholder="Production Subscription"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              {/* Subscription / Account ID */}
              <div>
                <label
                  htmlFor="provider_account_id"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  {form.provider === "azure"
                    ? "Subscription ID"
                    : "AWS Account ID"}
                </label>
                <input
                  id="provider_account_id"
                  type="text"
                  required
                  value={form.provider_account_id}
                  onChange={(e) =>
                    updateField("provider_account_id", e.target.value)
                  }
                  placeholder={
                    form.provider === "azure"
                      ? "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      : "123456789012"
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              {/* Credentials section */}
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-600 dark:bg-gray-900/50">
                <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
                  {form.provider === "azure"
                    ? "Azure Service Principal"
                    : "AWS Credentials"}
                </h3>

                {form.provider === "azure" ? (
                  <>
                    <div className="mb-3">
                      <label
                        htmlFor="azure_tenant_id"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Azure Tenant ID
                      </label>
                      <input
                        id="azure_tenant_id"
                        type="text"
                        required
                        value={form.tenant_id}
                        onChange={(e) =>
                          updateField("tenant_id", e.target.value)
                        }
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div className="mb-3">
                      <label
                        htmlFor="azure_client_id"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Client ID (App ID)
                      </label>
                      <input
                        id="azure_client_id"
                        type="text"
                        required
                        value={form.client_id}
                        onChange={(e) =>
                          updateField("client_id", e.target.value)
                        }
                        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="azure_client_secret"
                        className="block text-sm text-gray-600 dark:text-gray-400"
                      >
                        Client Secret
                      </label>
                      <input
                        id="azure_client_secret"
                        type="password"
                        required
                        value={form.client_secret}
                        onChange={(e) =>
                          updateField("client_secret", e.target.value)
                        }
                        placeholder="••••••••••••"
                        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                      />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-500">
                    AWS credential configuration coming soon.
                  </p>
                )}
              </div>

              {/* Test Connection */}
              {form.provider === "azure" && (
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={isTestingConnection || !isTestConnectionReady}
                    className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  >
                    {isTestingConnection ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <RefreshCw size={14} />
                        Test Connection
                      </>
                    )}
                  </button>
                  {testConnectionResult && (
                    <div
                      className={`rounded-lg px-4 py-3 text-sm ${
                        testConnectionResult.success
                          ? "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
                          : "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
                      }`}
                    >
                      {testConnectionResult.message}
                    </div>
                  )}
                </div>
              )}

              {/* Error message */}
              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false);
                    setForm(EMPTY_FORM);
                    setFormError(null);
                    setTestConnectionResult(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Adding..." : "Add Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Webhook Modal */}
      {showWebhookModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Webhook
              </h2>
              <button
                onClick={() => {
                  setShowWebhookModal(false);
                  setWebhookForm({
                    url: "",
                    secret: "",
                    events: [],
                    description: "",
                  });
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddWebhook} className="space-y-4">
              <div>
                <label
                  htmlFor="wh_url"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Webhook URL
                </label>
                <input
                  id="wh_url"
                  type="url"
                  required
                  value={webhookForm.url}
                  onChange={(e) =>
                    setWebhookForm((p) => ({ ...p, url: e.target.value }))
                  }
                  placeholder="https://example.com/webhook"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label
                  htmlFor="wh_desc"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Description (optional)
                </label>
                <input
                  id="wh_desc"
                  type="text"
                  value={webhookForm.description}
                  onChange={(e) =>
                    setWebhookForm((p) => ({
                      ...p,
                      description: e.target.value,
                    }))
                  }
                  placeholder="Slack notification channel"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Events
                </label>
                <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
                  Select which events trigger this webhook
                </p>
                <div className="space-y-2">
                  {ALLOWED_EVENTS.map((ev) => (
                    <label
                      key={ev}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        checked={webhookForm.events.includes(ev)}
                        onChange={() => toggleWebhookEvent(ev)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-mono text-xs">{ev}</span>
                      <span className="text-xs text-gray-400">
                        {ev === "scan.completed" &&
                          "- Scan finished successfully"}
                        {ev === "scan.failed" && "- Scan encountered an error"}
                        {ev === "finding.high" &&
                          "- High-severity findings detected"}
                        {ev === "finding.critical_change" &&
                          "- Critical finding status changed"}
                      </span>
                    </label>
                  ))}
                </div>
                {webhookForm.events.length === 0 && (
                  <p className="mt-1 text-xs text-red-500">
                    Select at least one event.
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="wh_secret"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Signing Secret (optional)
                </label>
                <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                  Used to generate HMAC-SHA256 signature header
                </p>
                <input
                  id="wh_secret"
                  type="password"
                  value={webhookForm.secret}
                  onChange={(e) =>
                    setWebhookForm((p) => ({ ...p, secret: e.target.value }))
                  }
                  placeholder="your-signing-secret"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
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
                    setShowWebhookModal(false);
                    setWebhookForm({
                      url: "",
                      secret: "",
                      events: [],
                      description: "",
                    });
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || webhookForm.events.length === 0}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Webhook"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Slack Integration Modal */}
      {showSlackModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Slack Integration
              </h2>
              <button
                onClick={() => {
                  setShowSlackModal(false);
                  setSlackForm({
                    webhook_url: "",
                    channel_name: "",
                    events: [],
                  });
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleAddSlack} className="space-y-4">
              <div>
                <label
                  htmlFor="slack_url"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Slack Webhook URL
                </label>
                <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                  Create an Incoming Webhook in your Slack workspace settings
                </p>
                <input
                  id="slack_url"
                  type="url"
                  required
                  value={slackForm.webhook_url}
                  onChange={(e) =>
                    setSlackForm((p) => ({
                      ...p,
                      webhook_url: e.target.value,
                    }))
                  }
                  placeholder="https://hooks.slack.com/services/T.../B.../..."
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label
                  htmlFor="slack_channel"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Channel Name (display only)
                </label>
                <div className="relative mt-1">
                  <Hash
                    size={14}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                  />
                  <input
                    id="slack_channel"
                    type="text"
                    value={slackForm.channel_name}
                    onChange={(e) =>
                      setSlackForm((p) => ({
                        ...p,
                        channel_name: e.target.value,
                      }))
                    }
                    placeholder="security-alerts"
                    className="w-full rounded-lg border border-gray-300 py-2 pl-8 pr-3 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Events
                </label>
                <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
                  Select which events trigger Slack notifications
                </p>
                <div className="space-y-2">
                  {SLACK_EVENTS.map((ev) => (
                    <label
                      key={ev}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        checked={slackForm.events.includes(ev)}
                        onChange={() => toggleSlackEvent(ev)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-mono text-xs">{ev}</span>
                      <span className="text-xs text-gray-400">
                        {ev === "scan.completed" &&
                          "- Scan finished successfully"}
                        {ev === "scan.failed" && "- Scan encountered an error"}
                        {ev === "finding.high" &&
                          "- High-severity findings detected"}
                        {ev === "finding.critical_change" &&
                          "- Critical finding status changed"}
                      </span>
                    </label>
                  ))}
                </div>
                {slackForm.events.length === 0 && (
                  <p className="mt-1 text-xs text-red-500">
                    Select at least one event.
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
                    setShowSlackModal(false);
                    setSlackForm({
                      webhook_url: "",
                      channel_name: "",
                      events: [],
                    });
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || slackForm.events.length === 0}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Add Integration"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create API Key Modal */}
      {showApiKeyModal && !createdApiKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Create API Key
              </h2>
              <button
                onClick={() => {
                  setShowApiKeyModal(false);
                  setApiKeyForm({
                    name: "",
                    scopes: ["read"],
                    expires_in_days: "",
                  });
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateApiKey} className="space-y-4">
              <div>
                <label
                  htmlFor="ak_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Name
                </label>
                <input
                  id="ak_name"
                  type="text"
                  required
                  maxLength={100}
                  value={apiKeyForm.name}
                  onChange={(e) =>
                    setApiKeyForm((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="CI/CD Pipeline Key"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Scopes
                </label>
                <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">
                  Select the permissions for this key
                </p>
                <div className="space-y-2">
                  {ALLOWED_SCOPES.map((scope) => (
                    <label
                      key={scope}
                      className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        checked={apiKeyForm.scopes.includes(scope)}
                        onChange={() => toggleApiKeyScope(scope)}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium">{scope}</span>
                      <span className="text-xs text-gray-400">
                        {scope === "read" &&
                          "- Read assets, findings, controls"}
                        {scope === "write" && "- Create and modify resources"}
                        {scope === "scan" && "- Trigger scans"}
                      </span>
                    </label>
                  ))}
                </div>
                {apiKeyForm.scopes.length === 0 && (
                  <p className="mt-1 text-xs text-red-500">
                    Select at least one scope.
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="ak_expiry"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Expiration (optional)
                </label>
                <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">
                  Leave empty for a non-expiring key
                </p>
                <select
                  id="ak_expiry"
                  value={apiKeyForm.expires_in_days}
                  onChange={(e) =>
                    setApiKeyForm((p) => ({
                      ...p,
                      expires_in_days: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="">No expiration</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                  <option value="180">180 days</option>
                  <option value="365">1 year</option>
                </select>
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
                    setShowApiKeyModal(false);
                    setApiKeyForm({
                      name: "",
                      scopes: ["read"],
                      expires_in_days: "",
                    });
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || apiKeyForm.scopes.length === 0}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Key"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* API Key Created — show full key once */}
      {createdApiKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                API Key Created
              </h2>
            </div>

            <div className="mb-4 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 dark:border-yellow-600 dark:bg-yellow-900/20">
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">
                Copy your API key now. It will not be shown again.
              </p>
            </div>

            <div className="mb-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Name
              </label>
              <p className="text-sm text-gray-900 dark:text-gray-100">
                {createdApiKey.name}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                API Key
              </label>
              <div className="mt-1 flex items-center gap-2">
                <code className="flex-1 break-all rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 font-mono text-sm dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100">
                  {createdApiKey.api_key}
                </code>
                <button
                  onClick={() => handleCopyApiKey(createdApiKey.api_key)}
                  className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                  title="Copy to clipboard"
                >
                  <Copy size={14} />
                  {copiedKey ? "Copied" : "Copy"}
                </button>
              </div>
            </div>

            <div className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              <p>
                Use this key in the <code>Authorization</code> header:
              </p>
              <code className="mt-1 block rounded-lg bg-gray-100 px-3 py-2 text-xs dark:bg-gray-900 dark:text-gray-300">
                Authorization: Bearer {createdApiKey.key_prefix}...
              </code>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => {
                  setCreatedApiKey(null);
                  setShowApiKeyModal(false);
                }}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Scheduled Report Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl dark:bg-gray-800">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Add Scheduled Report
              </h2>
              <button
                onClick={() => {
                  setShowScheduleModal(false);
                  setFormError(null);
                }}
                className="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateScheduledReport} className="space-y-4">
              <div>
                <label
                  htmlFor="sr_name"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Name
                </label>
                <input
                  id="sr_name"
                  type="text"
                  required
                  maxLength={100}
                  value={scheduleForm.name}
                  onChange={(e) =>
                    setScheduleForm((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="Weekly Executive Summary"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label
                  htmlFor="sr_type"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Report Type
                </label>
                <select
                  id="sr_type"
                  value={scheduleForm.report_type}
                  onChange={(e) =>
                    setScheduleForm((p) => ({
                      ...p,
                      report_type: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="executive_summary">Executive Summary</option>
                  <option value="compliance">Compliance</option>
                  <option value="technical_detail">Technical Detail</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="sr_schedule"
                  className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Schedule
                </label>
                <select
                  id="sr_schedule"
                  value={scheduleForm.schedule}
                  onChange={(e) =>
                    setScheduleForm((p) => ({
                      ...p,
                      schedule: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                >
                  <option value="daily">Daily (midnight UTC)</option>
                  <option value="weekly">Weekly (Monday midnight UTC)</option>
                  <option value="monthly">Monthly (1st of month UTC)</option>
                </select>
              </div>

              {/* Conditional config options based on report type */}
              {scheduleForm.report_type === "compliance" && (
                <div>
                  <label
                    htmlFor="sr_framework"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Compliance Framework
                  </label>
                  <select
                    id="sr_framework"
                    value={scheduleForm.config_framework}
                    onChange={(e) =>
                      setScheduleForm((p) => ({
                        ...p,
                        config_framework: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  >
                    <option value="cis_azure">CIS Azure</option>
                    <option value="soc2">SOC 2</option>
                    <option value="nist">NIST CSF</option>
                    <option value="iso27001">ISO 27001</option>
                  </select>
                </div>
              )}

              {scheduleForm.report_type === "technical_detail" && (
                <div>
                  <label
                    htmlFor="sr_severity"
                    className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                  >
                    Severity Filter (optional)
                  </label>
                  <select
                    id="sr_severity"
                    value={scheduleForm.config_severity}
                    onChange={(e) =>
                      setScheduleForm((p) => ({
                        ...p,
                        config_severity: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-900 dark:text-white"
                  >
                    <option value="">All severities</option>
                    <option value="high">High only</option>
                    <option value="medium">Medium only</option>
                    <option value="low">Low only</option>
                  </select>
                </div>
              )}

              {formError && (
                <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowScheduleModal(false);
                    setFormError(null);
                  }}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !scheduleForm.name.trim()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Create Schedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
}

// -- Scan Schedule per-account row ----------------------------------------

const SCHEDULE_PRESETS: { label: string; value: string }[] = [
  { label: "Disabled", value: "" },
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily (midnight)", value: "0 0 * * *" },
  { label: "Weekly (Sunday)", value: "0 0 * * 0" },
];

function ScanScheduleRow({
  account,
  onUpdated,
}: {
  account: CloudAccount;
  onUpdated: () => void;
}) {
  const current = account.scan_schedule;
  const [schedule, setSchedule] = useState(current ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isDirty = schedule !== (current ?? "");

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await api.put(`/accounts/${account.id}/schedule`, {
        scan_schedule: schedule || null,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onUpdated();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setSaveError(
        axiosErr.response?.data?.detail ?? "Failed to save schedule.",
      );
      setTimeout(() => setSaveError(null), 5000);
    } finally {
      setSaving(false);
    }
  };

  const presetMatch = SCHEDULE_PRESETS.find((p) => p.value === schedule);

  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div className="flex items-center gap-3">
        <Calendar size={16} className="text-gray-400 dark:text-gray-500" />
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {account.display_name}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {current ? `Schedule: ${current}` : "No schedule set"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <select
          value={presetMatch ? schedule : "__custom__"}
          onChange={(e) => {
            if (e.target.value !== "__custom__") {
              setSchedule(e.target.value);
            }
          }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
        >
          {SCHEDULE_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
          {!presetMatch && schedule && (
            <option value="__custom__">Custom: {schedule}</option>
          )}
        </select>
        {isDirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        )}
        {saved && (
          <span className="text-xs text-green-600 dark:text-green-400">
            Saved
          </span>
        )}
        {saveError && (
          <span className="text-xs text-red-600 dark:text-red-400">
            {saveError}
          </span>
        )}
      </div>
    </div>
  );
}
