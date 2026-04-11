# Roadmap

This roadmap is a public snapshot of where NimbusGuard is and where it's
going. It is **not a promise** — order and scope may shift based on
customer feedback, blockers, and security disclosures. For a detailed
log of what has shipped, see [CHANGELOG.md](../CHANGELOG.md).

Last updated: **2026-04-11**.

---

## Shipped

### Core platform

- [x] Multi-tenant architecture (tenant isolation at every query)
- [x] JWT auth (httpOnly cookies) + refresh tokens + bcrypt password hashing
- [x] SSO/OIDC (Azure AD, Okta, Google Workspace, custom OIDC providers)
- [x] MFA (TOTP + backup codes)
- [x] Custom RBAC roles beyond admin/viewer
- [x] Team invitations with role-based onboarding
- [x] API keys for CI/CD and programmatic access
- [x] Audit log with filter + export (admin only)
- [x] Dark / light theme

### Cloud coverage

- [x] Azure Resource Graph collector
- [x] Azure Defender for Cloud secure score + recommendations
- [x] **159 Azure check evaluators** across 34 resource types
- [x] **20 AWS check evaluators** (IAM, S3, EC2, RDS, VPC, CloudTrail, GuardDuty, Lambda)
- [x] Azure subscription-level state collector
      (Defender plans, security contacts, auto-provisioning, RBAC owners)
- [x] Cross-resource diagnostic settings collector (10 resource types)

### Security feature set

- [x] **Priority / Triage layer (P0..P3)** with transparent yaml-driven
      3×3 matrix + internet exposure bump
- [x] Dashboard priority overview card with Secure Score projection bar
- [x] Top 5 remediation groups ("fix this week" action plan)
- [x] Findings priority column + priority filter + remediation group filter
- [x] Dedicated `/scans` page with history, filters, and live
      5-second auto-polling
- [x] PDF evidence export (tenant-branded, per-scan or per-compliance)
- [x] Jira integration (push finding → ticket)
- [x] Slack integration (scan completion notifications)
- [x] Scheduled scans via Celery Beat (cron-based)
- [x] Bulk operations — waive, comment, assign findings at scale
- [x] Exception model with expiry + reviewer + audit trail

### Operations

- [x] Docker Compose for local + production
- [x] Alembic migrations with production-gated manual review
- [x] Trivy image scan in CI with `.trivyignore` for documented unpatchable CVEs
- [x] Prometheus `/metrics` endpoint
- [x] Health check `/health` verifying DB + Redis, 503 on degraded
- [x] Prod deployment behind Caddy with automatic TLS

---

## In progress

### Next sprint

- [ ] **Smart alerting** — Slack / email / webhook notifications on scan
      completion, filtered by priority (_"only notify me on new P0"_).
      Builds directly on the Priority layer — without triage, alerts are
      noise; with triage, they become a ranked action queue.
- [ ] **Remediation playbooks** — bulk Jira ticket creation from a single
      remediation group; one-click auto-remediation for selected groups
      (VNet restriction, diagnostic setting attachment, TLS hardening).

### Near-term backlog

- [ ] **Defender assessment enricher** — read
      `Microsoft.Security/assessments` for subscriptions where the
      collector detects Defender is ON, unlocking ~10 extra
      sub-assessments per subscription.
- [ ] **Entra ID / Microsoft Graph collector** — tenant-level MFA
      controls (CIS-AZ-01, 02), Conditional Access policies, PIM status.
      Blocked on granting `Directory.Read.All` + `Policy.Read.All` to the
      service principal.
- [ ] **Scan drill-down page `/scans/{id}`** — delta findings vs previous
      scan, pass/fail donut, deep-link into findings filtered by scan.
- [ ] **Onboarding UX polish** — copy-paste CLI for service principal,
      inline validation of permissions, explicit confirm step showing
      which subscriptions will be scanned.

---

## Planned

### Cloud expansion

- [ ] **GCP support** — Cloud Asset Inventory collector + CIS GCP
      benchmark evaluators. 4+ weeks of effort; deliberately deferred
      until Azure and AWS breadth are saturated.
- [ ] **Kubernetes support** — CIS Kubernetes Benchmark + Pod Security
      Standards. Targets bring-your-own-kubeconfig for AKS / EKS / GKE.

### Advanced controls

- [ ] **RBAC least-privilege deep checks** — stale role assignments,
      over-privileged service principals, custom role wildcard
      permissions, orphan permissions after user offboarding.
- [ ] **Terraform / IaC scanning** — scan Terraform plans in CI and
      attribute findings to the PR that introduced them. Shift-left on
      drift.
- [ ] **Custom policy engine (OPA / Rego)** — let customers write their
      own policies in Rego and run them against the asset inventory
      without forking the check registry.

### Enterprise features

- [ ] **SCIM user provisioning** — for Okta / Azure AD / OneLogin
      customers that mandate SCIM.
- [ ] **Forgot password flow** — currently only admins can reset user
      passwords; add email-token-based self-service.
- [ ] **Grafana stack + alerting** — Loki for operational logs,
      dashboards for API latency / scan queue depth / tenant activity.
- [ ] **Multi-region deployment** — per-tenant data residency (EU vs US),
      replicated reads.

---

## Explicitly rejected / deferred

These have been considered and rejected — either because the value is
too low, the effort is too high for the expected return, or the feature
fights our positioning. Listed here for transparency so contributors
don't propose them again unless the premise has changed.

- **ML-based priority scoring** — rejected in favour of the transparent
  yaml matrix. The entire competitive position of the Priority layer
  depends on being inspectable and customisable; an ML model defeats
  that.
- **Standalone Azure Policy compliance collector** — 50+ extra checks
  but changes the product model from posture to policy assignment,
  without improving signal/noise. Reconsider if a customer asks.
- **Gamification (streaks, badges, leaderboards)** — risks making a
  security product feel unserious. Secure Score projection already
  gives a clear improvement target.
- **Snooze / accept risk workflow** — already handled by the `Exception`
  model with expiry, reviewer, and audit trail.
- **Historical priority trend chart** — needs a time-series schema and
  more scan history than most tenants have. Will revisit once
  customers accumulate 3+ months of scans.
- **Free tier control expansion past ~200 checks** — diminishing
  returns; prospects stop counting. Focus instead on signal quality
  (triage, grouping, remediation playbooks).

---

## Known issues / tech debt

- **Trivy allow-list** — `.trivyignore` contains 2 accepted-risk HIGH
  CVEs (ncurses `CVE-2025-69720`, systemd `CVE-2026-29111`) waiting for
  Debian upstream patches. Periodically re-check and remove entries as
  they are fixed.
- **CI backend job runtime** — 1273 tests take ~10 minutes. Main
  bottlenecks are tenant-isolation test setup (~1s per test × 19 tests)
  and coverage instrumentation (~25% overhead). `pytest-xdist`
  parallelization was attempted but blocked on per-worker DB isolation
  — tracked as a future refactor.
- **Dependabot queue** — ~10 open vulnerability advisories on transitive
  dependencies, all LOW/MEDIUM with no reachable exploit path from our
  code. Clean-up sprint planned after smart alerting.

---

## How to influence the roadmap

- **File a feature request** on GitHub with a clear use case.
- **Drop into the discussions tab** with "what would you pay for
  next?" — customer feedback has pushed more than half of the last
  three sprints.
- **Open a draft PR** if you want to prototype. Check
  [CONTRIBUTING.md](CONTRIBUTING.md) first.
