// ── Severity & Status ────────────────────────────────────────────────

export type Severity = "high" | "medium" | "low";

export type FindingStatus = "pass" | "fail" | "error" | "not_applicable";

export type CloudProvider = "azure" | "aws";

export type TimeRange = "7d" | "14d" | "30d" | "90d";

// ── Core domain interfaces ───────────────────────────────────────────

export interface Asset {
  id: string;
  provider_id: string;
  resource_type: string;
  name: string;
  region: string | null;
  tags: Record<string, string> | null;
  first_seen_at: string;
  last_seen_at: string;
  cloud_account_id: string;
}

export interface Finding {
  id: string;
  status: FindingStatus;
  severity: Severity;
  title: string;
  dedup_key: string;
  waived: boolean;
  first_detected_at: string;
  last_evaluated_at: string;
  cloud_account_id: string;
  asset_id: string | null;
  control_id: string | null;
  scan_id: string | null;
  assigned_to: string | null;
  assignee_email: string | null;
  assignee_name: string | null;
  jira_ticket_key: string | null;
  jira_ticket_url: string | null;
}

export interface CloudAccount {
  id: string;
  provider: CloudProvider;
  display_name: string;
  provider_account_id: string;
  status: string;
  metadata_: Record<string, unknown> | null;
  last_scan_at: string | null;
  scan_schedule: string | null;
  created_at: string;
}

export interface Control {
  id: string;
  code: string;
  name: string;
  description: string;
  severity: Severity;
  framework: string;
  remediation_hint: string | null;
  provider_check_ref: Record<string, string> | null;
  framework_mappings: Record<string, string[]> | null;
}

export interface ControlWithCounts extends Control {
  pass_count: number;
  fail_count: number;
  total_count: number;
}

// ── Dashboard ────────────────────────────────────────────────────────

export interface DashboardSummary {
  secure_score: number | null;
  total_assets: number;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  top_failing_controls: FailingControl[];
  assets_by_type: Record<string, number>;
}

export interface FailingControl {
  code: string;
  name: string;
  severity: string;
  fail_count: number;
  total_count: number;
}

// ── API response wrappers ────────────────────────────────────────────

export interface PaginationMeta {
  total: number;
  page: number;
  size: number;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  meta: PaginationMeta | null;
}

// ── Auth types ───────────────────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  tenant_name: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
  mfa_enabled: boolean;
}

// ── MFA types ─────────────────────────────────────────────────────────

export interface MfaSetupResponse {
  secret: string;
  provisioning_uri: string;
}

export interface MfaBackupCodesResponse {
  backup_codes: string[];
}

export interface MfaRequiredResponse {
  mfa_required: boolean;
  mfa_token: string;
}

export interface TenantUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  role_id: string | null;
  role_name: string | null;
  is_active: boolean;
  created_at: string;
}

// ── Roles & Permissions ─────────────────────────────────────────────

export interface Role {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PermissionInfo {
  permission: string;
  description: string;
  category: string;
}

export interface PermissionListResponse {
  permissions: PermissionInfo[];
  categories: Record<string, string[]>;
}

export interface TrendPoint {
  date: string;
  high: number;
  medium: number;
  low: number;
}

export interface TrendResponse {
  data: TrendPoint[];
  period: string;
}

export interface ExceptionRecord {
  id: string;
  finding_id: string;
  reason: string;
  status: string;
  approved_by: string | null;
  expires_at: string | null;
  created_at: string;
}

// ── Similar findings ─────────────────────────────────────────────────

export interface SimilarFinding {
  id: string;
  severity: string;
  status: string;
  asset_name: string;
  asset_id: string;
  control_code: string;
  control_name: string;
  similarity_type: "same_control" | "same_asset";
  first_detected_at: string;
}

// ── Detail types (with relationships) ────────────────────────────────

export interface FindingDetail extends Finding {
  asset: Asset | null;
  control: Control | null;
}

export interface AssetDetail extends Asset {
  findings?: Finding[];
}

// ── Webhooks ────────────────────────────────────────────────────────

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
  description: string | null;
  last_triggered_at: string | null;
  last_status_code: number | null;
  created_at: string;
}

export interface WebhookTestResult {
  status_code: number;
  response_body: string;
  success: boolean;
}

// ── Audit ────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string;
  tenant_id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
  user_email: string | null;
}

// ── Finding events / timeline ───────────────────────────────────────

export interface FindingEvent {
  id: string;
  event_type: string;
  old_value: string | null;
  new_value: string | null;
  user_id: string | null;
  user_email: string | null;
  details: string | null;
  created_at: string;
}

// ── Finding comments ────────────────────────────────────────────────

export interface FindingComment {
  id: string;
  content: string;
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  created_at: string;
}

// ── API Keys ────────────────────────────────────────────────────────

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

// ── Compliance Trend ─────────────────────────────────────────────────

export interface ComplianceTrendPoint {
  date: string;
  score: number;
  passing: number;
  failing: number;
  total: number;
}

export interface ComplianceTrendResponse {
  data: ComplianceTrendPoint[];
  framework: string;
  period: string;
}

// ── Custom Frameworks ────────────────────────────────────────────────

export interface CustomFrameworkMapping {
  control_code: string;
  group: string;
  reference: string;
}

export interface CustomFramework {
  id: string;
  name: string;
  description: string | null;
  control_mappings: CustomFrameworkMapping[];
  is_active: boolean;
  created_at: string;
}

export interface ControlComplianceItem {
  control_code: string;
  control_name: string;
  severity: string;
  group: string;
  reference: string;
  pass_count: number;
  fail_count: number;
  total_count: number;
}

export interface CustomFrameworkCompliance {
  framework_id: string;
  framework_name: string;
  controls: ControlComplianceItem[];
  total_controls: number;
  passing_controls: number;
  failing_controls: number;
}

// ── Scheduled Reports ─────────────────────────────────────────────────

export interface ScheduledReport {
  id: string;
  name: string;
  report_type: string;
  schedule: string;
  config: Record<string, string>;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportHistoryEntry {
  id: string;
  scheduled_report_id: string;
  status: string;
  file_size: number | null;
  error_message: string | null;
  generated_at: string;
  created_at: string;
}

// -- Slack Integrations ─────────────────────────────────────────────

export interface SlackIntegration {
  id: string;
  webhook_url: string;
  channel_name: string | null;
  events: string[];
  is_active: boolean;
  created_by: string | null;
  created_at: string;
}

export interface SlackTestResult {
  success: boolean;
  response_body: string;
}

// -- Jira Integrations ─────────────────────────────────────────────

export interface JiraIntegration {
  id: string;
  base_url: string;
  email: string;
  project_key: string;
  issue_type: string;
  is_active: boolean;
  created_at: string;
}

export interface JiraTestResult {
  success: boolean;
  message: string;
  display_name?: string;
}

export interface JiraTicketResult {
  issue_key: string;
  issue_url: string;
  finding_id: string;
}

// -- Invitations ─────────────────────────────────────────────────────

export interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  invited_by: string | null;
}

export interface InvitationCreated {
  invitation: Invitation;
  invite_url: string;
}

// ── Custom Dashboards ───────────────────────────────────────────────

export interface DashboardWidget {
  widget: string;
  x: number;
  y: number;
  w: number;
  h: number;
  config: Record<string, unknown>;
}

export interface CustomDashboard {
  id: string;
  name: string;
  description: string | null;
  layout: DashboardWidget[];
  is_default: boolean;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface WidgetDataItem {
  widget: string;
  data: unknown;
}

export interface DashboardDataResponse {
  dashboard_id: string;
  widgets: WidgetDataItem[];
}

// -- SSO ─────────────────────────────────────────────────────────────

export type SsoProvider = "azure_ad" | "okta" | "google" | "custom_oidc";

export interface SsoConfig {
  id: string;
  provider: SsoProvider;
  client_id: string;
  issuer_url: string;
  metadata_url: string | null;
  domain_restriction: string | null;
  auto_provision: boolean;
  default_role: string;
  is_active: boolean;
}

export interface SsoPublicConfig {
  provider: SsoProvider;
  is_active: boolean;
}

export interface SsoTestResult {
  success: boolean;
  issuer: string | null;
  authorization_endpoint: string | null;
  token_endpoint: string | null;
  error: string | null;
}

// ── Asset Graph ────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  resource_type: string;
  provider: string;
  region: string | null;
  finding_count: number;
  highest_severity: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  nodes_by_provider: Record<string, number>;
  edges_by_type: Record<string, number>;
}

export interface AssetGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export interface RelatedAssetInfo {
  id: string;
  name: string;
  resource_type: string;
  provider: string;
}

export interface AssetRelationship {
  id: string;
  source_asset_id: string;
  target_asset_id: string;
  relationship_type: string;
  direction: string;
  related_asset: RelatedAssetInfo;
}

// ── Tenant Branding ─────────────────────────────────────────────────

export interface TenantBranding {
  logo_url: string | null;
  primary_color: string;
  company_name: string;
  favicon_url: string | null;
}

// ── Cross-Cloud Dashboard ──────────────────────────────────────────

export interface ProviderSummary {
  provider: string;
  display_name: string;
  accounts_count: number;
  total_assets: number;
  total_findings: number;
  findings_by_severity: Record<string, number>;
  secure_score: number | null;
  trend: string;
}

export interface CrossCloudTotals {
  accounts: number;
  assets: number;
  findings: number;
  overall_score: number | null;
  findings_by_severity: Record<string, number>;
}

export interface CrossCloudComparison {
  best_provider: string | null;
  worst_provider: string | null;
  score_gap: number;
}

export interface CrossCloudSummary {
  providers: ProviderSummary[];
  totals: CrossCloudTotals;
  comparison: CrossCloudComparison;
}
