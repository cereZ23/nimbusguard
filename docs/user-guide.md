# NimbusGuard User Guide

**Cloud Security Posture Management Platform**

Version 0.1.0 | Last updated: March 2026 | Built by [cerez23](https://github.com/cereZ23)

---

## Table of Contents

- [1. Getting Started](#1-getting-started)
  - [1.1 System Requirements](#11-system-requirements)
  - [1.2 Installation](#12-installation)
  - [1.3 First Login](#13-first-login)
- [2. Dashboard](#2-dashboard)
  - [2.1 Overview](#21-overview)
  - [2.2 Finding Trend Over Time](#22-finding-trend-over-time)
  - [2.3 Cross-Cloud Comparison](#23-cross-cloud-comparison)
  - [2.4 Custom Dashboards](#24-custom-dashboards)
- [3. Cloud Accounts](#3-cloud-accounts)
  - [3.1 Adding an Azure Account](#31-adding-an-azure-account)
  - [3.2 Adding an AWS Account](#32-adding-an-aws-account)
  - [3.3 Test Connection](#33-test-connection)
  - [3.4 Scan Scheduling](#34-scan-scheduling)
- [4. Assets](#4-assets)
  - [4.1 Asset Inventory](#41-asset-inventory)
  - [4.2 Asset Detail](#42-asset-detail)
  - [4.3 Asset Graph](#43-asset-graph)
- [5. Findings](#5-findings)
  - [5.1 Finding List](#51-finding-list)
  - [5.2 Finding Detail](#52-finding-detail)
  - [5.3 Bulk Actions](#53-bulk-actions)
  - [5.4 Requesting a Waiver](#54-requesting-a-waiver)
  - [5.5 Comments and Notes](#55-comments-and-notes)
  - [5.6 Finding Timeline](#56-finding-timeline)
- [6. Compliance](#6-compliance)
  - [6.1 Frameworks](#61-frameworks)
  - [6.2 Control Detail](#62-control-detail)
  - [6.3 Compliance Trend](#63-compliance-trend)
- [7. Reports and Export](#7-reports-and-export)
  - [7.1 PDF Evidence Pack](#71-pdf-evidence-pack)
  - [7.2 CSV and JSON Export](#72-csv-and-json-export)
  - [7.3 SIEM Export](#73-siem-export)
  - [7.4 Scheduled Reports](#74-scheduled-reports)
- [8. Integrations](#8-integrations)
  - [8.1 Webhooks](#81-webhooks)
  - [8.2 Slack](#82-slack)
  - [8.3 Jira](#83-jira)
  - [8.4 API Keys](#84-api-keys)
- [9. Settings and Administration](#9-settings-and-administration)
  - [9.1 User Management](#91-user-management)
  - [9.2 SSO/OIDC Configuration](#92-ssooidc-configuration)
  - [9.3 MFA Configuration](#93-mfa-configuration)
  - [9.4 Custom Roles (RBAC)](#94-custom-roles-rbac)
  - [9.5 Tenant Branding](#95-tenant-branding)
  - [9.6 Audit Logs](#96-audit-logs)
- [10. API Reference](#10-api-reference)
  - [10.1 Authentication](#101-authentication)
  - [10.2 Common Patterns](#102-common-patterns)
  - [10.3 Core Endpoints](#103-core-endpoints)
  - [10.4 Interactive Docs](#104-interactive-docs)
- [11. Environment Variables Reference](#11-environment-variables-reference)
- [12. Troubleshooting](#12-troubleshooting)

---

## 1. Getting Started

### 1.1 System Requirements

**Docker Compose deployment (recommended):**

| Component       | Minimum                |
| --------------- | ---------------------- |
| Docker          | 20.10 or later         |
| Docker Compose  | v2.0 or later          |
| RAM             | 4 GB available         |
| Disk            | 2 GB free              |
| Ports available | 3000, 5432, 6379, 8000 |

**Manual development setup:**

| Component  | Version       |
| ---------- | ------------- |
| Python     | 3.10 or later |
| Node.js    | 18 or later   |
| pnpm       | 8 or later    |
| PostgreSQL | 16            |
| Redis      | 7             |

### 1.2 Installation

#### Option A: Docker Compose (recommended)

This is the fastest way to get NimbusGuard running. Docker Compose starts PostgreSQL, Redis, the backend API, the Celery worker, and the frontend in one command.

**Step 1: Clone the repository**

```bash
git clone https://github.com/cereZ23/nimbusguard.git
cd nimbusguard
```

**Step 2: Create a backend environment file**

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set the required values:

```dotenv
# REQUIRED: Set a strong random key (minimum 32 characters)
SECRET_KEY=your-random-secret-key-minimum-32-chars

# REQUIRED: Fernet key for encrypting cloud credentials at rest
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CREDENTIAL_ENCRYPTION_KEY=your-fernet-key

# Keep defaults for Docker Compose
DATABASE_URL=postgresql+asyncpg://cspm:cspm@db:5432/cspm
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
DEBUG=false
```

**Step 3: Start all services**

```bash
docker compose up
```

This starts:

| Service       | Port | Purpose                    |
| ------------- | ---- | -------------------------- |
| Frontend (UI) | 3000 | Next.js web application    |
| Backend (API) | 8000 | FastAPI REST API           |
| PostgreSQL    | 5432 | Primary database           |
| Redis         | 6379 | Cache, message broker      |
| Celery Worker | --   | Background scan processing |

**Step 4: Run database migrations**

```bash
cd backend
alembic upgrade head
```

**Step 5: Open the application**

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

#### Option B: Manual setup (backend + frontend separately)

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
pnpm install
pnpm dev
```

Ensure PostgreSQL and Redis are running and accessible before starting the backend.

### 1.3 First Login

#### Registration (creates a tenant and admin user)

When you open NimbusGuard for the first time, you need to register an account. Registration creates both a **tenant** (your organization) and your **admin user** in one step.

1. Navigate to [http://localhost:3000](http://localhost:3000).
2. Click **Register**.
3. Fill in the registration form:
   - **Organization name** -- this becomes your tenant name.
   - **Full name** -- your display name.
   - **Email** -- used for login.
   - **Password** -- must be at least 8 characters and include uppercase, lowercase, digit, and special character.
4. Click **Create Account**.

You are automatically logged in and redirected to the dashboard.

**Password requirements:**

- Minimum 8 characters
- At least one lowercase letter
- At least one uppercase letter
- At least one digit
- At least one special character

Registration is rate-limited to 5 requests per hour per IP address.

#### Login flow

1. Navigate to [http://localhost:3000/login](http://localhost:3000/login).
2. Enter your email and password.
3. Click **Sign In**.

Login is rate-limited to 10 attempts per minute. After 5 failed login attempts, the account is locked for 15 minutes.

Authentication tokens are delivered via httpOnly secure cookies. The access token expires after 15 minutes and is automatically refreshed using the refresh token (valid for 7 days). Refresh tokens are rotated on each use for security.

#### MFA setup (recommended)

After logging in, it is strongly recommended that you enable Multi-Factor Authentication (MFA). See [Section 9.3](#93-mfa-configuration) for setup instructions.

---

## 2. Dashboard

### 2.1 Overview

The dashboard provides a high-level view of your cloud security posture. It is the first screen you see after login.

**Key components:**

- **Secure Score gauge** -- your overall security score as a percentage, calculated as `(passing checks / total checks) * 100`. This is derived from your most recent scan results.
- **KPI cards** -- summary counts for total assets, total findings, and a breakdown of findings by severity (high, medium, low).
- **Severity donut chart** -- visual distribution of open findings by severity level.
- **Top failing controls** -- the 5 controls with the most failures across your accounts. Each shows the control code, name, severity, and fail count.
- **Assets by type** -- top 10 resource types by count (e.g., `microsoft.storage/storageaccounts`, `aws.s3.bucket`).

Dashboard data is cached in Redis for 5 minutes. The cache is automatically invalidated when a scan completes.

### 2.2 Finding Trend Over Time

The trend view shows the count of new failing findings per day, broken down by severity.

Access it through the dashboard or directly via the API:

```
GET /api/v1/dashboard/trend?period=30d
```

Supported periods: any number of days in the format `Nd` (e.g., `7d`, `30d`, `90d`, `365d`). Maximum is 365 days.

### 2.3 Cross-Cloud Comparison

If you have accounts from multiple cloud providers, the cross-cloud view shows:

- Per-provider metrics (Azure vs AWS): account count, asset count, findings, secure score.
- Overall aggregated score weighted by asset count.
- Trend direction per provider (improving, stable, declining) based on the last two completed scans.
- Best and worst performing providers with score gap.

### 2.4 Custom Dashboards

Create custom dashboards tailored to specific teams or use cases.

1. Navigate to **Dashboard** and click **Custom Dashboards**.
2. Click **Create Dashboard** and give it a name and optional description.
3. Add widgets by selecting from available metric types.
4. Arrange and configure widgets as needed.
5. Share dashboards with other team members by granting access.

---

## 3. Cloud Accounts

Cloud accounts represent the connection between NimbusGuard and your cloud subscriptions. You must add at least one cloud account before running a scan.

### 3.1 Adding an Azure Account

#### Prerequisites

NimbusGuard requires **read-only** access to your Azure subscription. No write permissions are needed.

#### Step 1: Create an Azure AD App Registration

1. Open the [Azure Portal](https://portal.azure.com).
2. Navigate to **Azure Active Directory** (or **Microsoft Entra ID**) in the left sidebar.
3. Click **App registrations** in the left menu.
4. Click **New registration**.
5. Fill in the form:
   - **Name**: `NimbusGuard CSPM` (or any descriptive name).
   - **Supported account types**: select "Accounts in this organizational directory only."
   - **Redirect URI**: leave blank.
6. Click **Register**.
7. On the app overview page, copy the following values -- you will need them later:
   - **Application (client) ID**
   - **Directory (tenant) ID**

#### Step 2: Create a Client Secret

1. In the app registration, click **Certificates & secrets** in the left menu.
2. Click **New client secret**.
3. Enter a description (e.g., `NimbusGuard`) and select an expiration period.
4. Click **Add**.
5. **Copy the secret value immediately** -- it is shown only once.

#### Step 3: Assign Roles to the App Registration

1. Navigate to the **Subscription** you want to scan (or a **Management Group** if scanning multiple subscriptions).
2. Click **Access control (IAM)** in the left menu.
3. Click **Add** and select **Add role assignment**.
4. Assign the **Reader** role:
   - Role: `Reader`
   - Members: select the App Registration you created.
   - Click **Review + assign**.
5. Repeat to assign the **Security Reader** role:
   - Role: `Security Reader`
   - Members: select the same App Registration.
   - Click **Review + assign**.

These two roles provide:

| Role            | Purpose                                                       |
| --------------- | ------------------------------------------------------------- |
| Reader          | Resource inventory via Azure Resource Graph                   |
| Security Reader | Microsoft Defender for Cloud secure score and recommendations |

#### Step 4: Add the Account in NimbusGuard

1. In NimbusGuard, navigate to **Cloud Accounts**.
2. Click **Add Account**.
3. Select **Azure** as the provider.
4. Fill in the form:
   - **Display name**: a descriptive label (e.g., "Production Azure Subscription").
   - **Subscription ID**: your Azure subscription ID.
   - **Tenant ID**: the Directory (tenant) ID from step 1.
   - **Client ID**: the Application (client) ID from step 1.
   - **Client Secret**: the secret value from step 2.
5. Click **Test Connection** to verify credentials.
6. If the test succeeds, click **Save**.

### 3.2 Adding an AWS Account

#### Prerequisites

NimbusGuard requires **read-only** access to your AWS account. You can use either IAM user credentials or cross-account role assumption.

#### Option A: IAM User with Read-Only Access

1. Open the [AWS IAM Console](https://console.aws.amazon.com/iam/).
2. Navigate to **Users** and click **Create user**.
3. Enter a username (e.g., `nimbusguard-cspm`).
4. Click **Next**.
5. Select **Attach policies directly**.
6. Attach the following managed policies:
   - `ReadOnlyAccess` (or a more restrictive custom policy)
   - `SecurityAudit`
7. Click **Create user**.
8. Navigate to the user, select **Security credentials**, and create an **Access key**.
9. Select "Application running outside AWS" as the use case.
10. Copy the **Access key ID** and **Secret access key**.

#### Option B: Cross-Account IAM Role (recommended for production)

1. In the AWS account you want to scan, create an IAM role:
   - Navigate to **IAM** and click **Roles**, then **Create role**.
   - Select **Another AWS account** as the trusted entity type.
   - Enter the AWS account ID where NimbusGuard runs.
   - Attach the `ReadOnlyAccess` and `SecurityAudit` policies.
   - Name the role (e.g., `NimbusGuardCSPMRole`).
   - Copy the **Role ARN** (e.g., `arn:aws:iam::123456789012:role/NimbusGuardCSPMRole`).
2. In NimbusGuard, provide IAM user credentials that have `sts:AssumeRole` permission for the target role, plus the Role ARN.

#### Add the Account in NimbusGuard

1. Navigate to **Cloud Accounts**.
2. Click **Add Account**.
3. Select **AWS** as the provider.
4. Fill in the form:
   - **Display name**: a descriptive label (e.g., "Production AWS Account").
   - **Account ID**: your AWS account number (e.g., `123456789012`).
   - **Access Key ID**: from your IAM user.
   - **Secret Access Key**: from your IAM user.
   - **Region**: your primary region (defaults to `us-east-1` if not specified).
   - **Role ARN** (optional): for cross-account role assumption.
5. Click **Test Connection** to verify credentials.
6. If the test succeeds, click **Save**.

### 3.3 Test Connection

Before saving an account, you can validate credentials without storing them:

- **Azure**: performs a Resource Graph query (`Resources | summarize count()`) to confirm access and reports the number of resources found.
- **AWS**: calls `sts:GetCallerIdentity` and `s3:ListBuckets` to confirm access and reports the number of S3 buckets found.

Test connection is stateless -- credentials are not persisted until you explicitly save the account.

### 3.4 Scan Scheduling

#### Manual Scan

Trigger a scan on-demand from the Cloud Accounts page:

1. Navigate to **Cloud Accounts**.
2. Click the **Scan** button next to the account.
3. The scan status changes to "pending" and then "running."

Scans are idempotent -- if a scan is already in progress for an account, a new request returns HTTP 409 (Conflict).

#### Automated Scan Schedule

Set up recurring scans using cron expressions:

1. Navigate to **Cloud Accounts**.
2. Click on an account to open its settings.
3. Enter a **Scan Schedule** in cron format:

| Schedule          | Cron Expression | Description               |
| ----------------- | --------------- | ------------------------- |
| Every 6 hours     | `0 */6 * * *`   | Runs at :00 every 6 hours |
| Daily at midnight | `0 0 * * *`     | Once per day              |
| Daily at 2 AM     | `0 2 * * *`     | Common for off-peak scans |
| Every Monday 9 AM | `0 9 * * 1`     | Weekly on Monday          |
| Twice daily       | `0 6,18 * * *`  | 6 AM and 6 PM             |

4. Click **Save**.

Celery Beat checks for due scans every 60 seconds and dispatches them to the worker queue.

---

## 4. Assets

### 4.1 Asset Inventory

The Assets page shows a complete inventory of all cloud resources discovered during scans.

**Features:**

- **Search**: type in the search box to filter assets by name.
- **Filtering**: filter by resource type, region, or cloud account.
- **Sorting**: click column headers to sort by name, type, region, or last-seen date. The API supports `sort_by` and `sort_order` parameters.
- **Pagination**: navigate between pages with 20 items per page by default.

**Supported resource types** include:

| Provider | Examples                                                                                 |
| -------- | ---------------------------------------------------------------------------------------- |
| Azure    | Storage accounts, VMs, Key Vaults, Web Apps, SQL servers, Cosmos DB, AKS, NSGs, and more |
| AWS      | S3 buckets, EC2 instances, RDS databases, IAM users, Lambda functions, VPCs, and more    |

### 4.2 Asset Detail

Click any asset to see its detail page, which includes:

- **Properties and metadata**: resource name, type, region, provider ID, and raw cloud properties.
- **Associated findings**: all security findings related to this asset, with severity and status.
- **Cloud provider link**: direct link to the resource in the Azure Portal or AWS Console.

From the asset detail page, click any finding to navigate directly to its detail view.

### 4.3 Asset Graph

The asset graph visualizes relationships between resources in your cloud environment. This helps you understand dependencies and blast radius when a resource has a security finding.

Access the graph view from an asset's detail page or from the **Assets** section.

---

## 5. Findings

### 5.1 Finding List

The Findings page lists all security findings discovered by NimbusGuard's 100+ built-in security checks.

**Severity levels:**

| Level    | Description                                              |
| -------- | -------------------------------------------------------- |
| Critical | Immediate risk -- public exposure, missing encryption    |
| High     | Significant risk -- weak authentication, missing logging |
| Medium   | Moderate risk -- suboptimal configuration                |
| Low      | Minor risk -- best practice deviation                    |
| Info     | Informational -- no direct risk                          |

**Status values:**

| Status   | Description                               |
| -------- | ----------------------------------------- |
| Open     | Active finding requiring attention        |
| Pass     | Check passed -- resource is compliant     |
| Fail     | Check failed -- resource is non-compliant |
| Waived   | Finding has been waived via exception     |
| Resolved | Previously failing, now passing           |

**Filtering options:**

- Severity (critical, high, medium, low, info)
- Status (open, pass, fail, waived)
- Cloud account
- Asset
- Control
- Assigned user
- Date range (first detected from/to)
- Free text search (matches on title)

**Sorting:**

Click column headers to sort by title, severity, status, first detected date, or last evaluated date. Default sort is by last evaluated date, descending.

**Saved filters:**

Save frequently used filter combinations for quick access:

1. Set your desired filters.
2. Click **Save Filter**.
3. Give it a name (e.g., "Critical Azure findings").
4. Access saved filters from the dropdown next to the search bar.

### 5.2 Finding Detail

Click any finding to see its full detail, which includes:

- **Severity and status** with color-coded indicators.
- **Evidence**: the raw property values that triggered the finding, displayed as structured JSON.
- **Remediation guidance**: step-by-step instructions to fix the issue, plus Infrastructure-as-Code snippets when available:
  - **Terraform** code to remediate the issue.
  - **Bicep** template (for Azure resources).
  - **Azure CLI** commands (for Azure resources).
- **Control mapping**: the CIS Benchmark control this finding relates to, with framework mappings (SOC 2, NIST 800-53, ISO 27001).
- **Similar findings**: up to 10 related findings -- either the same control on other assets (same control, different resource) or other controls failing on the same asset.
- **Assigned user**: who is responsible for remediation.
- **Comments**: team discussion thread.
- **Timeline**: full history of status changes, assignments, waiver requests, and comments.

### 5.3 Bulk Actions

Select multiple findings using checkboxes and apply actions in batch:

- **Bulk waive**: request waivers for multiple findings at once. Provide a reason that applies to all selected findings.
- **Bulk assign**: assign multiple findings to a team member.

Findings that already have an active or approved waiver are automatically skipped during bulk waive operations.

### 5.4 Requesting a Waiver

Waivers allow you to acknowledge a finding and document why remediation is not feasible or not required.

**Waiver workflow:**

1. From the finding detail page, click **Request Waiver**.
2. Enter a justification explaining why this finding should be waived.
3. Submit the request. The waiver status becomes "requested."
4. An admin reviews the waiver and either approves or rejects it.
5. If approved, the finding status changes to "waived."

Waiver requests are tracked in the finding timeline and audit log.

### 5.5 Comments and Notes

Add comments to findings for team collaboration:

1. Open a finding's detail page.
2. Scroll to the **Comments** section.
3. Type your comment and click **Add Comment**.
4. Comments include the author's name, email, and timestamp.

Only the comment author or an admin can delete a comment.

### 5.6 Finding Timeline

Every finding maintains a complete activity log:

| Event Type       | Description                                 |
| ---------------- | ------------------------------------------- |
| status_changed   | Finding status changed (e.g., fail to pass) |
| assigned         | Finding assigned to a user                  |
| unassigned       | Assignment removed                          |
| waiver_requested | Waiver request submitted                    |
| commented        | Comment added                               |

Access the timeline from the finding detail page under the **Timeline** tab.

---

## 6. Compliance

### 6.1 Frameworks

NimbusGuard maps security findings to recognized compliance frameworks:

| Framework           | Description                                           |
| ------------------- | ----------------------------------------------------- |
| CIS Azure Benchmark | 84 controls mapped from CIS v3.0 for Azure            |
| CIS AWS Benchmark   | 20 controls mapped from CIS v3.0 for AWS              |
| SOC 2 Type II       | Service organization control criteria (CC series)     |
| NIST 800-53         | Federal information security controls (SC, AC, etc.)  |
| ISO 27001           | International information security standard (Annex A) |
| Custom Frameworks   | Create your own frameworks and map controls           |

Each security check is mapped to one or more framework controls via the `control_mappings.yaml` configuration.

**Custom frameworks:**

1. Navigate to **Compliance** and click **Custom Frameworks**.
2. Click **Create Framework**.
3. Define framework name, description, and version.
4. Map existing controls to your custom framework sections.
5. Use custom frameworks in compliance reporting.

### 6.2 Control Detail

Click any control to see:

- **Control code and name** (e.g., CIS-AZ-01: Ensure Storage account HTTPS-only transfer).
- **Severity** level.
- **Pass/fail breakdown**: count of resources passing and failing this control.
- **Affected resources**: drill-down to the specific findings for this control.
- **Framework mappings**: which SOC 2, NIST, and ISO 27001 controls this maps to.
- **Remediation hint**: high-level guidance on how to fix the issue.

### 6.3 Compliance Trend

Track your compliance score over time:

```
GET /api/v1/dashboard/compliance-trend?framework=cis_azure&period=30d
```

Supported frameworks: `cis_azure`, `soc2`, `nist`, `iso27001`.

The trend shows daily snapshots of passing controls, failing controls, total controls, and compliance score percentage.

---

## 7. Reports and Export

### 7.1 PDF Evidence Pack

Generate a comprehensive PDF report suitable for auditors and management.

The PDF evidence pack includes:

- **Summary table**: total findings, failures, passing, broken down by severity.
- **Findings detail**: every finding with its title, severity, status, control code, asset name, region, detection dates, remediation hints, and evidence snapshots.
- **Formatted for print**: A4 layout with color-coded severity indicators.

**To generate a PDF:**

1. Navigate to **Reports** or **Findings**.
2. Apply any desired filters (severity, status, account).
3. Click **Export** and select **PDF**.
4. The PDF downloads automatically.

**Via API:**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/findings?format=pdf&severity=high" \
  -o cspm-report.pdf
```

### 7.2 CSV and JSON Export

Export findings data for processing in spreadsheets or external tools.

**CSV export:**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/findings?format=csv" \
  -o findings-export.csv
```

The CSV includes columns: ID, Title, Status, Severity, Waived, First Detected, Last Evaluated, Asset Name, Asset Type, Asset Region, Control Code, Control Name, Control Severity, Cloud Account ID.

**JSON export:**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/findings?format=json" \
  -o findings-export.json
```

All export formats support the following filters as query parameters:

| Parameter    | Description                | Example             |
| ------------ | -------------------------- | ------------------- |
| `severity`   | Filter by severity level   | `severity=high`     |
| `status`     | Filter by finding status   | `status=fail`       |
| `account_id` | Filter by cloud account ID | `account_id=<uuid>` |

Maximum export size is 10,000 findings per request. Export endpoints are rate-limited to 10 requests per minute.

### 7.3 SIEM Export

Export findings in formats compatible with Security Information and Event Management (SIEM) platforms.

**CEF (Common Event Format)** -- for ArcSight, Splunk, Microsoft Sentinel:

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/siem/cef" \
  -o findings-export.cef
```

**LEEF (Log Event Extended Format)** -- for IBM QRadar:

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/siem/leef" \
  -o findings-export.leef
```

**JSON Lines (NDJSON)** -- for Splunk HEC, Sentinel, Elasticsearch:

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/export/siem/jsonl" \
  -o findings-export.jsonl
```

All SIEM export endpoints accept additional filters:

| Parameter    | Description             |
| ------------ | ----------------------- |
| `severity`   | Filter by severity      |
| `status`     | Filter by status        |
| `account_id` | Filter by account       |
| `date_from`  | ISO 8601 datetime start |
| `date_to`    | ISO 8601 datetime end   |

### 7.4 Scheduled Reports

Set up automatic report delivery via email:

1. Navigate to **Reports** and click **Scheduled Reports**.
2. Click **Create Schedule**.
3. Configure:
   - **Report type**: compliance, findings, or evidence pack.
   - **Filters**: severity, status, accounts.
   - **Schedule**: cron expression for delivery frequency.
   - **Recipients**: email addresses.
4. Click **Save**.

Scheduled reports require SMTP configuration (see [Environment Variables](#11-environment-variables-reference)). If SMTP is not configured, report delivery is logged instead of sent.

---

## 8. Integrations

### 8.1 Webhooks

Webhooks notify external systems when events occur in NimbusGuard.

**Supported event types:**

| Event                     | Description                                       |
| ------------------------- | ------------------------------------------------- |
| `scan.completed`          | A scan finished successfully                      |
| `scan.failed`             | A scan encountered an error                       |
| `finding.high`            | A new high-severity finding was detected          |
| `finding.critical_change` | A finding's severity or status changed critically |

**Creating a webhook:**

1. Navigate to **Settings** then **Webhooks**.
2. Click **Create Webhook**.
3. Fill in:
   - **URL**: the HTTPS endpoint to receive payloads (must start with `https://` or `http://`).
   - **Secret** (optional): used to sign payloads with HMAC for verification.
   - **Events**: select which events trigger this webhook.
   - **Description** (optional): a label for your reference.
4. Click **Save**.

**Testing a webhook:**

After creating a webhook, click the **Test** button to send a test payload. The response status code and body are displayed so you can verify delivery.

**Via API:**

```bash
# Create a webhook
curl -b cookies.txt -X POST \
  http://localhost:8000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.example.com/webhook",
    "secret": "your-signing-secret",
    "events": ["scan.completed", "finding.high"],
    "description": "Production notifications"
  }'

# Test the webhook
curl -b cookies.txt -X POST \
  http://localhost:8000/api/v1/webhooks/<webhook-id>/test
```

### 8.2 Slack

Send finding notifications directly to Slack channels.

1. Navigate to **Settings** then **Integrations** then **Slack**.
2. Configure the Slack integration:
   - **Webhook URL**: your Slack incoming webhook URL.
   - **Channel**: target channel for notifications.
   - **Notification rules**: which severity levels and events trigger Slack messages.
3. Click **Save** and **Test** to verify the connection.

### 8.3 Jira

Create Jira tickets directly from findings for tracking remediation in your project management workflow.

1. Navigate to **Settings** then **Integrations** then **Jira**.
2. Configure:
   - **Jira URL**: your Jira instance URL.
   - **Project key**: the Jira project where tickets will be created.
   - **Authentication credentials**: API token or OAuth.
   - **Default issue type**: Story, Bug, Task, etc.
   - **Field mappings**: map NimbusGuard severity to Jira priority.
3. Click **Save** and **Test**.

Once configured, a **Create Jira Ticket** button appears on finding detail pages.

### 8.4 API Keys

API keys provide programmatic access for CI/CD pipelines, scripts, and third-party integrations.

**Creating an API key:**

1. Navigate to **Settings** then **API Keys**.
2. Click **Create API Key**.
3. Fill in:
   - **Name**: a descriptive label (e.g., "CI/CD Pipeline").
   - **Scopes**: the permissions granted to this key.
   - **Expiration** (optional): number of days until the key expires.
4. Click **Create**.
5. **Copy the full API key immediately** -- it is displayed only once.

The key is displayed with a prefix (e.g., `ng_...`) for identification and a hashed value is stored in the database.

**Using an API key:**

Include the API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer ng_your-api-key-here" \
  http://localhost:8000/api/v1/findings?severity=high
```

**Revoking an API key:**

1. Navigate to **Settings** then **API Keys**.
2. Click the **Revoke** button next to the key you want to disable.
3. The key is permanently deleted and can no longer be used.

---

## 9. Settings and Administration

### 9.1 User Management

#### Inviting Users

Administrators can invite team members to join the tenant:

1. Navigate to **Settings** then **Users**.
2. Click **Invite User**.
3. Enter the user's email address and select a role.
4. Click **Send Invitation**.

The invited user receives an email (or a logged invitation link if SMTP is not configured) with a link to accept the invitation and create their account.

**Invitation management:**

- **Resend**: send a new invitation link if the original expired.
- **Revoke**: cancel a pending invitation.
- Invitations that are accepted or revoked cannot be reused.

#### Role Assignment

NimbusGuard includes two built-in roles:

| Role   | Capabilities                                                 |
| ------ | ------------------------------------------------------------ |
| Admin  | Full access: manage accounts, users, settings, trigger scans |
| Viewer | Read-only: view dashboard, assets, findings, reports         |

Admins can also create custom roles with granular permissions (see [Section 9.4](#94-custom-roles-rbac)).

### 9.2 SSO/OIDC Configuration

NimbusGuard supports Single Sign-On via OpenID Connect (OIDC) for the following identity providers:

- **Azure Active Directory (Microsoft Entra ID)**
- **Okta**
- **Google Workspace**
- **Any OIDC-compliant provider**

#### Setup Steps

1. Navigate to **Settings** then **SSO Configuration**.
2. Click **Configure SSO**.
3. Fill in:
   - **Provider**: select your identity provider.
   - **Client ID**: the application/client ID from your IdP.
   - **Client Secret**: the client secret from your IdP.
   - **Issuer URL**: the OIDC issuer URL (e.g., `https://login.microsoftonline.com/<tenant-id>/v2.0` for Azure AD).
   - **Metadata URL** (optional): the OIDC discovery endpoint URL if different from the standard `.well-known` path.
   - **Domain restriction** (optional): restrict SSO login to specific email domains (e.g., `example.com`).
   - **Auto-provision**: whether to automatically create user accounts on first SSO login.
   - **Default role**: the role assigned to auto-provisioned users (e.g., "viewer").
4. Click **Save** (this saves but does not activate).
5. Click **Test Connection** to verify OIDC discovery works.
6. If the test succeeds, enable SSO by toggling it to **Active**.

**Azure AD example configuration:**

| Field        | Value                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------ |
| Provider     | `azure_ad`                                                                                 |
| Client ID    | Application (client) ID from Azure AD App Registration                                     |
| Issuer URL   | `https://login.microsoftonline.com/<your-tenant-id>/v2.0`                                  |
| Metadata URL | `https://login.microsoftonline.com/<your-tenant-id>/v2.0/.well-known/openid-configuration` |

**Okta example configuration:**

| Field      | Value                                           |
| ---------- | ----------------------------------------------- |
| Provider   | `okta`                                          |
| Client ID  | Application client ID from Okta                 |
| Issuer URL | `https://<your-domain>.okta.com/oauth2/default` |

SSO login flow:

1. User navigates to the login page and clicks **Sign in with SSO**.
2. User is redirected to the IdP authorization page.
3. After authenticating, the IdP redirects back to NimbusGuard.
4. NimbusGuard exchanges the authorization code for tokens and creates a session.
5. User lands on the dashboard.

### 9.3 MFA Configuration

Multi-Factor Authentication adds a second layer of security using Time-based One-Time Passwords (TOTP).

**Setting up MFA:**

1. Log in to NimbusGuard.
2. Navigate to **Settings** then **Security** (or **Profile**).
3. Click **Enable MFA**.
4. NimbusGuard generates a secret key and displays a QR code.
5. Scan the QR code with your authenticator app:
   - Google Authenticator
   - Authy
   - Microsoft Authenticator
   - 1Password
   - Any TOTP-compatible app
6. Enter the 6-digit code from your authenticator app to verify.
7. NimbusGuard displays **backup codes** -- store these securely. Each backup code can only be used once.

**Logging in with MFA:**

1. Enter your email and password as usual.
2. When prompted, enter the 6-digit code from your authenticator app.
3. Alternatively, enter one of your backup codes (8-character hex codes).

MFA login attempts are rate-limited to 5 attempts per token (5-minute window). If exceeded, you must log in again.

**Disabling MFA:**

1. Navigate to **Settings** then **Security**.
2. Click **Disable MFA**.
3. Enter your password to confirm.

### 9.4 Custom Roles (RBAC)

Create granular roles beyond the built-in admin and viewer roles.

**Creating a custom role:**

1. Navigate to **Settings** then **Roles**.
2. Click **Create Role**.
3. Enter a **name** and **description**.
4. Select **permissions** from the available categories.
5. Click **Save**.

Permissions are organized by category. You can view all available permissions via the API:

```bash
curl -b cookies.txt http://localhost:8000/api/v1/roles/permissions
```

**Assigning a custom role:**

When inviting a user or editing an existing user, select the custom role from the role dropdown.

System roles (admin, viewer) cannot be modified or deleted. Custom roles can be updated or deleted at any time by an admin.

### 9.5 Tenant Branding

Customize the appearance of NimbusGuard for your organization:

1. Navigate to **Settings** then **Branding**.
2. Upload your **company logo**.
3. Set custom **primary colors**.
4. Click **Save**.

NimbusGuard also supports **dark/light mode** via the theme toggle in the top navigation bar. The preference is stored in your browser's local storage.

### 9.6 Audit Logs

Every significant action in NimbusGuard is recorded in the audit log.

**Tracked actions include:**

| Action                | Description                        |
| --------------------- | ---------------------------------- |
| `user.login`          | Successful login (standard or MFA) |
| `user.sso_login`      | Successful SSO login               |
| `account.create`      | Cloud account created              |
| `account.delete`      | Cloud account deleted              |
| `scan.trigger`        | Scan manually triggered            |
| `finding.assign`      | Finding assigned to a user         |
| `finding.comment.add` | Comment added to a finding         |
| `webhook.create`      | Webhook created                    |
| `api_key.create`      | API key created                    |
| `api_key.revoke`      | API key revoked                    |
| `invitation.created`  | User invitation sent               |
| `sso.config.created`  | SSO configuration created          |
| `sso.config.updated`  | SSO configuration updated          |

**Viewing audit logs:**

1. Navigate to **Settings** then **Audit Logs** (admin only).
2. Filter by action type or resource type.
3. Each entry shows: timestamp, user email, action, resource, detail, and IP address.

**Via API:**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/audit-logs?action=user.login&page=1&size=50"
```

---

## 10. API Reference

NimbusGuard exposes a RESTful JSON API. All endpoints are prefixed with `/api/v1/`.

### 10.1 Authentication

NimbusGuard uses JWT (JSON Web Tokens) delivered via httpOnly secure cookies.

**Register a new account:**

```bash
curl -c cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecureP@ss123",
    "full_name": "Admin User",
    "tenant_name": "My Organization"
  }'
```

**Login:**

```bash
curl -c cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecureP@ss123"
  }'
```

If MFA is enabled, the login response includes `mfa_required: true` and a temporary `mfa_token`. Complete the MFA challenge:

```bash
curl -c cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/mfa/login \
  -H "Content-Type: application/json" \
  -d '{
    "mfa_token": "<token-from-login-response>",
    "code": "123456"
  }'
```

**Token refresh:**

Access tokens expire after 15 minutes. The refresh token (valid 7 days) is automatically included in the cookie. To refresh manually:

```bash
curl -b cookies.txt -c cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/refresh
```

**Logout:**

```bash
curl -b cookies.txt -X POST \
  http://localhost:8000/api/v1/auth/logout
```

This revokes the refresh token and clears the auth cookies.

**Get current user:**

```bash
curl -b cookies.txt http://localhost:8000/api/v1/auth/me
```

### 10.2 Common Patterns

**Response envelope:**

All API responses follow a consistent structure:

```json
{
  "data": { ... },
  "error": null,
  "meta": null
}
```

- `data`: the response payload (object, array, or null).
- `error`: error message string (null on success).
- `meta`: pagination metadata (null for non-paginated responses).

**Pagination:**

Paginated endpoints accept `page` and `size` query parameters:

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/findings?page=2&size=50"
```

Response includes pagination metadata:

```json
{
  "data": [ ... ],
  "error": null,
  "meta": {
    "total": 342,
    "page": 2,
    "size": 50
  }
}
```

**Sorting:**

Sortable endpoints accept `sort_by` and `sort_order` parameters:

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/findings?sort_by=severity&sort_order=desc"
```

Supported sort fields vary by endpoint. For findings: `title`, `severity`, `status`, `first_detected_at`, `last_evaluated_at`.

**Rate limiting:**

| Endpoint             | Limit          |
| -------------------- | -------------- |
| Registration         | 5 per hour     |
| Login                | 10 per minute  |
| Scan trigger         | 60 per hour    |
| Export (all formats) | 10 per minute  |
| MFA login            | 10 per minute  |
| General API          | 100 per minute |

When rate-limited, the API returns HTTP 429 (Too Many Requests) with a `Retry-After` header.

**Error responses:**

```json
{
  "data": null,
  "error": "Finding not found",
  "meta": null
}
```

Standard HTTP status codes:

| Code | Meaning                             |
| ---- | ----------------------------------- |
| 200  | Success                             |
| 201  | Created                             |
| 204  | No Content (successful deletion)    |
| 400  | Bad Request (validation failed)     |
| 401  | Unauthorized (invalid credentials)  |
| 403  | Forbidden (insufficient role)       |
| 404  | Not Found                           |
| 409  | Conflict (duplicate resource)       |
| 422  | Unprocessable Entity (domain error) |
| 429  | Too Many Requests (rate limited)    |

### 10.3 Core Endpoints

| Method   | Endpoint                            | Auth Required | Description                                      |
| -------- | ----------------------------------- | ------------- | ------------------------------------------------ |
| `POST`   | `/auth/register`                    | No            | Register tenant + admin user                     |
| `POST`   | `/auth/login`                       | No            | Authenticate and receive JWT cookies             |
| `POST`   | `/auth/refresh`                     | Cookie        | Refresh access token                             |
| `POST`   | `/auth/logout`                      | Cookie        | Revoke refresh token and clear cookies           |
| `GET`    | `/auth/me`                          | Yes           | Get current user profile                         |
| `POST`   | `/auth/mfa/setup`                   | Yes           | Initiate MFA setup                               |
| `POST`   | `/auth/mfa/verify`                  | Yes           | Complete MFA setup with TOTP code                |
| `POST`   | `/auth/mfa/login`                   | No            | Complete MFA challenge during login              |
| `POST`   | `/auth/mfa/disable`                 | Yes           | Disable MFA (requires password)                  |
| `GET`    | `/accounts`                         | Yes           | List cloud accounts                              |
| `POST`   | `/accounts`                         | Admin         | Create a cloud account                           |
| `GET`    | `/accounts/:id`                     | Yes           | Get a cloud account                              |
| `DELETE` | `/accounts/:id`                     | Admin         | Delete a cloud account                           |
| `PUT`    | `/accounts/:id/schedule`            | Admin         | Update scan schedule                             |
| `POST`   | `/accounts/test-connection`         | Admin         | Test cloud provider credentials                  |
| `GET`    | `/assets`                           | Yes           | List assets (paginated, filterable)              |
| `GET`    | `/assets/:id`                       | Yes           | Get asset detail                                 |
| `GET`    | `/assets/:id/graph`                 | Yes           | Get asset relationship graph                     |
| `GET`    | `/findings`                         | Yes           | List findings (paginated, filterable, sortable)  |
| `GET`    | `/findings/:id`                     | Yes           | Get finding detail                               |
| `GET`    | `/findings/:id/remediation`         | Yes           | Get remediation snippets (Terraform, Bicep, CLI) |
| `GET`    | `/findings/:id/similar`             | Yes           | Get similar findings                             |
| `PUT`    | `/findings/:id/assign`              | Yes           | Assign a finding to a user                       |
| `POST`   | `/findings/bulk-waive`              | Yes           | Bulk waive findings                              |
| `GET`    | `/findings/:id/comments`            | Yes           | List comments on a finding                       |
| `POST`   | `/findings/:id/comments`            | Yes           | Add a comment to a finding                       |
| `DELETE` | `/findings/:id/comments/:commentId` | Yes           | Delete a comment                                 |
| `GET`    | `/findings/:id/timeline`            | Yes           | Get finding event timeline                       |
| `GET`    | `/controls`                         | Yes           | List all controls                                |
| `GET`    | `/dashboard/summary`                | Yes           | Get dashboard summary                            |
| `GET`    | `/dashboard/trend`                  | Yes           | Get finding trend over time                      |
| `GET`    | `/dashboard/compliance-trend`       | Yes           | Get compliance score trend                       |
| `GET`    | `/dashboard/cross-cloud`            | Yes           | Get cross-cloud comparison                       |
| `POST`   | `/scans`                            | Admin         | Trigger a scan                                   |
| `GET`    | `/scans/:id`                        | Yes           | Get scan status                                  |
| `GET`    | `/export/findings`                  | Yes           | Export findings (JSON, CSV, or PDF)              |
| `GET`    | `/export/siem/cef`                  | Yes           | Export in CEF format                             |
| `GET`    | `/export/siem/leef`                 | Yes           | Export in LEEF format                            |
| `GET`    | `/export/siem/jsonl`                | Yes           | Export in JSON Lines format                      |
| `CRUD`   | `/webhooks`                         | Admin         | Manage webhooks                                  |
| `POST`   | `/webhooks/:id/test`                | Admin         | Test a webhook                                   |
| `GET`    | `/webhooks/events`                  | Admin         | List allowed webhook event types                 |
| `CRUD`   | `/api-keys`                         | Admin         | Manage API keys                                  |
| `CRUD`   | `/roles`                            | Admin (write) | Manage custom roles                              |
| `GET`    | `/roles/permissions`                | Yes           | List all available permissions                   |
| `CRUD`   | `/invitations`                      | Admin         | Manage team invitations                          |
| `POST`   | `/invitations/accept`               | No            | Accept an invitation                             |
| `CRUD`   | `/sso/config`                       | Admin         | Manage SSO configuration                         |
| `POST`   | `/sso/test`                         | Admin         | Test SSO OIDC discovery                          |
| `GET`    | `/audit-logs`                       | Admin         | View audit log entries                           |
| `CRUD`   | `/custom-frameworks`                | Admin         | Manage custom compliance frameworks              |
| `CRUD`   | `/custom-dashboards`                | Yes           | Manage custom dashboards                         |
| `CRUD`   | `/saved-filters`                    | Yes           | Manage saved finding filters                     |
| `CRUD`   | `/scheduled-reports`                | Admin         | Manage scheduled report delivery                 |
| `CRUD`   | `/integrations/slack`               | Admin         | Manage Slack integration                         |
| `CRUD`   | `/integrations/jira`                | Admin         | Manage Jira integration                          |
| `CRUD`   | `/branding`                         | Admin         | Manage tenant branding                           |

**Example: Trigger a scan**

```bash
curl -b cookies.txt -X POST \
  http://localhost:8000/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "<account-uuid>",
    "scan_type": "full"
  }'
```

Response:

```json
{
  "data": {
    "id": "a1b2c3d4-...",
    "cloud_account_id": "...",
    "scan_type": "full",
    "status": "pending",
    "created_at": "2026-03-09T10:30:00Z"
  },
  "error": null,
  "meta": null
}
```

**Example: List findings with filters**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/findings?severity=high&status=fail&sort_by=last_evaluated_at&sort_order=desc&page=1&size=20"
```

**Example: Get finding remediation snippets**

```bash
curl -b cookies.txt \
  "http://localhost:8000/api/v1/findings/<finding-uuid>/remediation"
```

Response:

```json
{
  "data": {
    "control_code": "CIS-AZ-01",
    "control_name": "Ensure Storage account HTTPS-only transfer",
    "description": "Storage account should enforce HTTPS-only traffic",
    "remediation_hint": "Enable 'Secure transfer required' in the storage account settings",
    "snippets": {
      "terraform": "resource \"azurerm_storage_account\" \"example\" {\n  enable_https_traffic_only = true\n}",
      "bicep": "resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {\n  properties: {\n    supportsHttpsTrafficOnly: true\n  }\n}",
      "azure_cli": "az storage account update --name <account-name> --https-only true"
    }
  },
  "error": null,
  "meta": null
}
```

### 10.4 Interactive Docs

NimbusGuard provides interactive API documentation via Swagger UI.

- **Swagger UI**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **OpenAPI spec (JSON)**: [http://localhost:8000/api/openapi.json](http://localhost:8000/api/openapi.json)

The Swagger UI allows you to explore all endpoints, view request/response schemas, and make test requests directly from the browser.

---

## 11. Environment Variables Reference

All configuration is managed via environment variables. These are loaded from a `.env` file in the `backend/` directory or from the system environment.

### Application

| Variable     | Required   | Default                      | Description                                                                                                                               |
| ------------ | ---------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `SECRET_KEY` | Yes (prod) | Auto-generated in debug mode | JWT signing key. Must be a strong random string in production. The application refuses to start in non-debug mode with the default value. |
| `DEBUG`      | No         | `false`                      | Enable debug mode. When true, auto-generates an ephemeral secret key and relaxes cookie security. Never enable in production.             |
| `APP_NAME`   | No         | `CSPM API`                   | Application name displayed in API docs.                                                                                                   |

### Database

| Variable       | Required | Default                                              | Description                                                             |
| -------------- | -------- | ---------------------------------------------------- | ----------------------------------------------------------------------- |
| `DATABASE_URL` | No       | `postgresql+asyncpg://cspm:cspm@localhost:5432/cspm` | PostgreSQL connection string. Uses asyncpg driver for async operations. |

### Redis

| Variable    | Required | Default                    | Description                                     |
| ----------- | -------- | -------------------------- | ----------------------------------------------- |
| `REDIS_URL` | No       | `redis://localhost:6379/0` | Redis connection for caching and rate limiting. |

### Celery (Background Tasks)

| Variable                | Required | Default                    | Description                               |
| ----------------------- | -------- | -------------------------- | ----------------------------------------- |
| `CELERY_BROKER_URL`     | No       | `redis://localhost:6379/1` | Message broker URL for Celery task queue. |
| `CELERY_RESULT_BACKEND` | No       | `redis://localhost:6379/1` | Backend for storing Celery task results.  |

### JWT (Authentication)

| Variable                    | Required | Default | Description                       |
| --------------------------- | -------- | ------- | --------------------------------- |
| `JWT_ALGORITHM`             | No       | `HS256` | Algorithm used for JWT signing.   |
| `JWT_ACCESS_EXPIRE_MINUTES` | No       | `15`    | Access token lifetime in minutes. |
| `JWT_REFRESH_EXPIRE_DAYS`   | No       | `7`     | Refresh token lifetime in days.   |

### Azure (Global Defaults)

| Variable              | Required | Default | Description                                                     |
| --------------------- | -------- | ------- | --------------------------------------------------------------- |
| `AZURE_TENANT_ID`     | No       | Empty   | Default Azure AD tenant ID (can also be set per cloud account). |
| `AZURE_CLIENT_ID`     | No       | Empty   | Default Azure AD application client ID.                         |
| `AZURE_CLIENT_SECRET` | No       | Empty   | Default Azure AD client secret.                                 |

### Scanning

| Variable               | Required | Default | Description                                                 |
| ---------------------- | -------- | ------- | ----------------------------------------------------------- |
| `SCAN_TIMEOUT_SECONDS` | No       | `600`   | Maximum time (in seconds) for a single scan before timeout. |
| `SCAN_MAX_PER_HOUR`    | No       | `5`     | Maximum scans per hour per account.                         |

### Rate Limiting

| Variable                | Required | Default | Description                        |
| ----------------------- | -------- | ------- | ---------------------------------- |
| `RATE_LIMIT_PER_MINUTE` | No       | `100`   | Default API rate limit per minute. |

### CORS

| Variable       | Required | Default                     | Description                                                                   |
| -------------- | -------- | --------------------------- | ----------------------------------------------------------------------------- |
| `CORS_ORIGINS` | No       | `["http://localhost:3000"]` | Allowed CORS origins (JSON array). Add your frontend domain(s) in production. |

### Credential Encryption

| Variable                    | Required   | Default                      | Description                                                                                                                                                               |
| --------------------------- | ---------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CREDENTIAL_ENCRYPTION_KEY` | Yes (prod) | Auto-generated in debug mode | Fernet key used to encrypt cloud provider credentials at rest. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### SMTP (Email)

| Variable        | Required | Default              | Description                                                          |
| --------------- | -------- | -------------------- | -------------------------------------------------------------------- |
| `SMTP_HOST`     | No       | Empty                | SMTP server hostname. When empty, emails are logged instead of sent. |
| `SMTP_PORT`     | No       | `587`                | SMTP server port (587 for TLS, 465 for SSL).                         |
| `SMTP_USER`     | No       | Empty                | SMTP authentication username.                                        |
| `SMTP_PASSWORD` | No       | Empty                | SMTP authentication password.                                        |
| `SMTP_FROM`     | No       | `noreply@cspm.local` | Sender email address for outgoing emails.                            |

### Frontend

| Variable       | Required | Default                 | Description                                                                                                                        |
| -------------- | -------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `FRONTEND_URL` | No       | `http://localhost:3000` | Base URL for the frontend. Used to build invitation links and SSO callback URLs. Set this to your production domain in deployment. |

---

## 12. Troubleshooting

### Common Errors and Solutions

#### "SECRET_KEY is set to the insecure default value"

**Cause:** You are running in non-debug mode without setting a `SECRET_KEY`.

**Fix:** Set a strong random `SECRET_KEY` in your `.env` file:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add the output to your `.env` file as `SECRET_KEY=<generated-value>`.

#### "A scan is already in progress for this account" (HTTP 409)

**Cause:** You attempted to trigger a scan while another scan is still running or pending for the same account.

**Fix:** Wait for the current scan to complete, or check scan status:

```bash
curl -b cookies.txt http://localhost:8000/api/v1/scans/<scan-id>
```

#### "Invalid email or password" (HTTP 401)

**Cause:** The email or password is incorrect, or the account may be locked.

**Fix:**

- Verify your email and password.
- If your account is locked (after 5 failed attempts), wait 15 minutes for the lockout to expire.
- Contact an admin to check account status.

#### "Too Many Requests" (HTTP 429)

**Cause:** You have exceeded the rate limit for this endpoint.

**Fix:** Wait the duration indicated in the `Retry-After` response header before retrying.

#### Azure connection test fails

**Cause:** Incorrect credentials or insufficient permissions.

**Fix:**

1. Verify the Tenant ID, Client ID, Client Secret, and Subscription ID.
2. Confirm the App Registration has `Reader` and `Security Reader` roles on the target subscription.
3. Check that the client secret has not expired in Azure AD.

#### AWS connection test fails

**Cause:** Incorrect credentials or insufficient permissions.

**Fix:**

1. Verify the Access Key ID and Secret Access Key.
2. If using a role ARN, confirm the IAM user has `sts:AssumeRole` permission.
3. Check that the IAM user has `ReadOnlyAccess` and `SecurityAudit` policies attached.
4. Verify the access key is active (not deactivated) in the IAM Console.

#### Dashboard shows no data

**Cause:** No scans have been completed yet, or no cloud accounts are configured.

**Fix:**

1. Add a cloud account (see [Section 3](#3-cloud-accounts)).
2. Trigger a scan.
3. Wait for the scan to complete (check scan status).
4. Refresh the dashboard.

#### Invitation emails not being delivered

**Cause:** SMTP is not configured.

**Fix:**

- Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in your `.env` file.
- When SMTP is not configured, invitation links are logged to the application logs instead of emailed. Check logs for the invitation URL.

#### SSO login fails with "auth_failed"

**Cause:** The OIDC provider returned an error or the configuration is incorrect.

**Fix:**

1. Check the backend logs for the detailed SSO error message (details are logged server-side for security).
2. Verify your SSO configuration: Issuer URL, Client ID, Client Secret.
3. Use the **Test Connection** button in SSO settings to verify OIDC discovery.
4. Ensure the redirect URI in your IdP matches: `<FRONTEND_URL>/api/v1/auth/sso/callback`.

### Logs Location

**Docker Compose:**

```bash
# View backend logs
docker compose logs backend

# View Celery worker logs
docker compose logs celery-worker

# Follow logs in real-time
docker compose logs -f backend

# View all service logs
docker compose logs
```

**Manual setup:**

Backend logs are output to stdout in structured JSON format. Each log entry includes:

- `timestamp` -- ISO 8601 datetime.
- `level` -- log level (INFO, WARNING, ERROR).
- `request_id` -- unique ID for request tracing.
- `tenant_id` -- tenant context (when available).
- `user_id` -- authenticated user (when available).
- `message` -- log message.

### Health Check Endpoint

Verify that the backend is running and healthy:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{ "status": "ok" }
```

Docker Compose is configured with health checks for all services:

| Service       | Health Check            | Interval |
| ------------- | ----------------------- | -------- |
| PostgreSQL    | `pg_isready -U cspm`    | 5s       |
| Redis         | `redis-cli ping`        | 5s       |
| Backend       | `HTTP GET /health`      | 10s      |
| Celery Worker | `celery inspect ping`   | 30s      |
| Frontend      | `HTTP GET /` (via wget) | 10s      |

### Getting Help

- **API documentation**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs) (Swagger UI)
- **Source code**: [https://github.com/cereZ23/nimbusguard](https://github.com/cereZ23/nimbusguard)

---

_NimbusGuard -- Cloud Security Posture Management Platform. Built by [cerez23](https://github.com/cereZ23)._
