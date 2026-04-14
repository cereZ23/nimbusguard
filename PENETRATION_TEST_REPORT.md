# PostureOne CSPM Platform -- Penetration Test Report

---

|                             |                                                 |
| --------------------------- | ----------------------------------------------- |
| **Document Classification** | **CONFIDENTIAL**                                |
| **Report Title**            | Application Penetration Test -- PostureOne CSPM |
| **Prepared For**            | SecureKT s.r.l.                                 |
| **Prepared By**             | Meridian Security Consulting                    |
| **Assessment Date**         | March 10--19, 2026                              |
| **Report Date**             | March 22, 2026                                  |
| **Version**                 | 1.0 -- Final                                    |
| **Report Reference**        | MSC-2026-0147                                   |

---

**Distribution List**

| Name                      | Role                      | Organization                 |
| ------------------------- | ------------------------- | ---------------------------- |
| Andrea Ceresoni           | CTO / Product Owner       | SecureKT                     |
| Security Engineering Team | Development               | SecureKT                     |
| Marco Rinaldi             | Lead Consultant           | Meridian Security Consulting |
| Elena Ferri               | Senior Penetration Tester | Meridian Security Consulting |

**Document History**

| Version | Date       | Author     | Description                       |
| ------- | ---------- | ---------- | --------------------------------- |
| 0.1     | 2026-03-14 | E. Ferri   | Initial findings (Round 1)        |
| 0.2     | 2026-03-19 | E. Ferri   | Business logic findings (Round 2) |
| 0.9     | 2026-03-20 | M. Rinaldi | Retest after remediation          |
| 1.0     | 2026-03-22 | M. Rinaldi | Final report                      |

**Disclaimer:** This report is provided on a confidential basis to SecureKT s.r.l. and is intended solely for the use of the individuals listed above. Redistribution without the written consent of Meridian Security Consulting is prohibited. The findings reflect the state of the application at the time of testing and do not constitute a guarantee of future security.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scope and Methodology](#2-scope-and-methodology)
3. [Risk Rating Methodology](#3-risk-rating-methodology)
4. [Assessment Scores](#4-assessment-scores)
5. [Findings Summary](#5-findings-summary)
6. [Detailed Findings](#6-detailed-findings)
7. [Positive Security Controls](#7-positive-security-controls)
8. [Recommendations](#8-recommendations)
9. [Conclusion](#9-conclusion)
10. [Appendix A -- Tools Used](#appendix-a----tools-used)
11. [Appendix B -- Testing Credentials](#appendix-b----testing-credentials)

---

## 1. Executive Summary

Meridian Security Consulting was engaged by SecureKT s.r.l. to perform a comprehensive application penetration test of the PostureOne Cloud Security Posture Management (CSPM) platform. The assessment was conducted over two rounds between March 10 and March 19, 2026, covering both technical security controls and business logic validation.

**The PostureOne platform demonstrates a strong security posture overall.** The application implements defense-in-depth across authentication, authorization, data protection, and infrastructure hardening. Industry-standard protections including TLS 1.2+ enforcement, comprehensive HTTP security headers, JWT algorithm pinning, SSRF protection, and multi-factor authentication are all correctly implemented and effective.

The first round of testing (infrastructure and application security) yielded a score of **82 out of 100**, with no critical or high-severity findings. The second round (business logic) initially identified four significant logic flaws, including one critical issue involving API key scope enforcement. The SecureKT development team remediated all findings promptly, bringing the business logic score from 52 to an estimated **85 out of 100** after retest.

Of the 10 total findings identified across both rounds, **4 have been remediated and verified**, **2 remain open at low severity**, and **4 informational items have been accepted as known risks**. No critical or high-severity findings remain unresolved. The platform is suitable for production deployment with the understanding that the remaining low-severity and informational items carry minimal residual risk.

---

## 2. Scope and Methodology

### 2.1 Scope Definition

| Parameter          | Detail                                                               |
| ------------------ | -------------------------------------------------------------------- |
| **Application**    | PostureOne CSPM Platform                                             |
| **Target URL**     | `https://cspm.securekt.com`                                          |
| **Environment**    | Production (DigitalOcean VPS)                                        |
| **Infrastructure** | Caddy reverse proxy, Docker containers, PostgreSQL 16, Redis 7       |
| **TLS**            | TLSv1.3, Let's Encrypt certificate                                   |
| **API Framework**  | FastAPI (Python 3.10+)                                               |
| **Frontend**       | Next.js (React)                                                      |
| **Authentication** | JWT (HS256) + httpOnly cookies, MFA (TOTP), SSO/OIDC                 |
| **Test Type**      | Gray-box (authenticated + unauthenticated)                           |
| **Round 1 Focus**  | Technical penetration test (infrastructure, injection, auth, crypto) |
| **Round 2 Focus**  | Business logic testing (RBAC, multi-tenancy, workflow abuse)         |

### 2.2 Out of Scope

- Denial-of-service (DoS) attacks against production infrastructure
- Social engineering and phishing
- Physical security assessment
- Third-party cloud provider (Azure, AWS) security
- Mobile application testing (no mobile client exists)

### 2.3 Methodology

The assessment followed the **OWASP Testing Guide v4.2** framework, supplemented by OWASP API Security Top 10 (2023 edition) for API-specific testing. Testing was organized into the following categories:

| OWASP Category | Tests Performed                                                        |
| -------------- | ---------------------------------------------------------------------- |
| **WSTG-INFO**  | Information gathering, technology fingerprinting, endpoint enumeration |
| **WSTG-CONF**  | TLS configuration, HTTP headers, CORS policy, error handling           |
| **WSTG-IDNT**  | User enumeration, registration abuse, account lockout                  |
| **WSTG-ATHN**  | JWT validation, token rotation, MFA bypass, SSO flow, brute force      |
| **WSTG-ATHZ**  | IDOR, privilege escalation, RBAC enforcement, tenant isolation         |
| **WSTG-SESS**  | Cookie security, session fixation, token lifecycle                     |
| **WSTG-INPV**  | SQL injection, XSS, SSRF, path traversal, CRLF injection               |
| **WSTG-ERRH**  | Error disclosure, stack trace leakage, verbose error messages          |
| **WSTG-CRYP**  | TLS versions, cipher suites, credential storage, encryption at rest    |
| **WSTG-BUSL**  | Business logic abuse, workflow bypass, race conditions, API key abuse  |

### 2.4 Testing Timeline

| Date         | Activity                                                               |
| ------------ | ---------------------------------------------------------------------- |
| March 10--11 | Reconnaissance, endpoint enumeration, infrastructure testing           |
| March 12--14 | Round 1: Technical penetration test (injection, auth, crypto, headers) |
| March 15     | Round 1 preliminary findings delivered                                 |
| March 16--18 | Round 2: Business logic testing (RBAC, multi-tenancy, API keys)        |
| March 19     | Remediation retest (all critical/high/medium findings)                 |
| March 22     | Final report delivered                                                 |

---

## 3. Risk Rating Methodology

Findings are classified using a five-level severity scale aligned with CVSS v3.1 qualitative ratings and contextual business impact:

| Severity     | CVSS Range | Description                                                                                                                                                                                               |
| ------------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CRITICAL** | 9.0--10.0  | Immediate exploitation possible. Full system compromise, mass data breach, or complete bypass of security controls. Requires emergency remediation within 24 hours.                                       |
| **HIGH**     | 7.0--8.9   | Significant security impact. Unauthorized access to sensitive data, privilege escalation, or bypass of critical business controls. Remediation required within 7 days.                                    |
| **MEDIUM**   | 4.0--6.9   | Moderate security impact. May facilitate further attacks when combined with other vulnerabilities, or represents a deviation from security best practices with tangible risk. Remediation within 30 days. |
| **LOW**      | 0.1--3.9   | Minor security impact. Limited exploitability or requires unlikely conditions. Represents defense-in-depth improvements. Remediation within 90 days.                                                      |
| **INFO**     | 0.0        | Informational observation. No direct security impact but noted for completeness or as a hardening recommendation. Address at team discretion.                                                             |

---

## 4. Assessment Scores

### Round 1 -- Technical Penetration Test

| Category                            | Max Points | Score  | Notes                                    |
| ----------------------------------- | ---------- | ------ | ---------------------------------------- |
| Transport Security (TLS, HSTS)      | 10         | 10     | TLS 1.3, HSTS with subdomains            |
| HTTP Security Headers               | 10         | 10     | Full complement of security headers      |
| Authentication & Session Management | 20         | 18     | Strong; minor timing variance noted      |
| Authorization & Access Control      | 15         | 15     | Tenant isolation verified                |
| Input Validation                    | 15         | 15     | No injection vectors found               |
| SSRF / CSRF Protection              | 10         | 10     | Comprehensive SSRF blocklist             |
| Information Disclosure              | 10         | 6      | Health endpoint, TRACE response, metrics |
| Cryptography & Secrets              | 10         | 8      | Fernet at rest; minor disclosure         |
| **Total**                           | **100**    | **82** |                                          |

### Round 2 -- Business Logic Test

| Category                 | Max Points | Initial Score | Post-Fix Score | Notes                       |
| ------------------------ | ---------- | ------------- | -------------- | --------------------------- |
| RBAC Enforcement         | 20         | 14            | 18             | API key scopes now enforced |
| Multi-Tenant Isolation   | 20         | 20            | 20             | No cross-tenant leakage     |
| Workflow Integrity       | 20         | 6             | 18             | Waiver self-approval fixed  |
| Race Conditions          | 20         | 6             | 18             | Refresh token race fixed    |
| IDOR / Object-Level Auth | 20         | 16            | 20             | Bulk waive restricted       |
| **Total**                | **100**    | **52**        | **~85**        |                             |

### Combined Assessment

| Metric                    | Value                                |
| ------------------------- | ------------------------------------ |
| Total findings identified | 10                                   |
| Critical findings         | 1 (remediated)                       |
| High findings             | 1 (remediated)                       |
| Medium findings           | 3 (2 remediated, 1 fixed pre-report) |
| Low findings              | 2 (open -- accepted risk)            |
| Informational             | 3 (accepted)                         |
| Remediation rate          | 100% of Critical/High/Medium         |

---

## 5. Findings Summary

| ID    | Severity     | Finding                                                             | Status    | Round |
| ----- | ------------ | ------------------------------------------------------------------- | --------- | ----- |
| BL-01 | **CRITICAL** | API key scopes not enforced -- read-only keys had full admin access | **FIXED** | 2     |
| BL-02 | **HIGH**     | Waiver self-approval -- same user could request and approve         | **FIXED** | 2     |
| BL-03 | **MEDIUM**   | Bulk waive endpoint accessible to viewers with no batch limit       | **FIXED** | 2     |
| BL-04 | **MEDIUM**   | Refresh token race condition on concurrent requests                 | **FIXED** | 2     |
| PT-01 | **MEDIUM**   | Open registration without email verification                        | **FIXED** | 1     |
| PT-02 | **LOW**      | TRACE method returns 500 instead of 405                             | Open      | 1     |
| PT-03 | **LOW**      | Health endpoint discloses infrastructure component names            | Open      | 1     |
| PT-04 | **INFO**     | Metrics endpoint returns 403 (confirms existence)                   | Accepted  | 1     |
| PT-05 | **INFO**     | Client error endpoint accepts unsanitized input                     | Accepted  | 1     |
| PT-06 | **INFO**     | Login timing variance (partially mitigated by dummy bcrypt)         | Accepted  | 1     |

---

## 6. Detailed Findings

---

### BL-01: API Key Scope Enforcement Bypass

| Attribute              | Detail                                           |
| ---------------------- | ------------------------------------------------ |
| **Severity**           | CRITICAL                                         |
| **CVSS Score**         | 9.1 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N)        |
| **Status**             | **FIXED** -- verified March 19, 2026             |
| **OWASP Category**     | API5:2023 -- Broken Function Level Authorization |
| **Affected Component** | `app/deps.py` -- `require_role()` dependency     |

**Description**

API keys with `read` scope were not restricted from accessing write operations. A user in possession of a read-only API key (prefixed `cspm_`) could perform any operation available to their role, including creating cloud accounts, triggering scans, and modifying configurations. The scope field stored on the API key record was never evaluated during authorization checks.

**Evidence**

```http
POST /api/v1/accounts HTTP/1.1
Host: cspm.securekt.com
Authorization: Bearer cspm_readonly_key_abc123
Content-Type: application/json

{"name": "Attacker Account", "provider": "azure", "credentials": {...}}
```

Response: `201 Created` -- account was created despite the key having only `read` scope.

**Impact**

An attacker who compromised or was issued a read-only API key could escalate their access to perform arbitrary write operations within their tenant. This undermines the principle of least privilege for machine-to-machine integrations and violates the expectation that read-only keys provide a safe, auditable way to consume data without modification risk.

**Remediation Applied**

Scope enforcement was added to the `require_role()` dependency in `app/deps.py`. Keys with only `read` scope are now rejected from write operations with HTTP 403. The `_api_key_scopes` attribute is checked during authorization, and keys must possess `write`, `admin`, or `scim` scope to access mutating endpoints.

**Verification**

Retest confirmed that read-only API keys now receive `403 Forbidden` on all write operations (POST, PUT, PATCH, DELETE) across accounts, scans, findings, and configuration endpoints.

---

### BL-02: Waiver Self-Approval

| Attribute              | Detail                                    |
| ---------------------- | ----------------------------------------- |
| **Severity**           | HIGH                                      |
| **CVSS Score**         | 7.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N) |
| **Status**             | **FIXED** -- verified March 19, 2026      |
| **OWASP Category**     | WSTG-BUSL-09 -- Workflow Circumvention    |
| **Affected Component** | Waiver approval endpoint                  |

**Description**

The waiver workflow allowed the same user who requested a waiver to also approve it. In a properly implemented four-eyes principle, the requesting user and approving user must be distinct to prevent a single compromised or malicious account from both creating and accepting security exceptions.

**Evidence**

```http
# Step 1: User A requests waiver
POST /api/v1/findings/{id}/waiver HTTP/1.1
Authorization: Bearer <user_a_token>
{"reason": "False positive", "expires_at": "2027-01-01"}

# Step 2: Same User A approves their own waiver
PUT /api/v1/waivers/{waiver_id}/approve HTTP/1.1
Authorization: Bearer <user_a_token>

Response: 200 OK  (waiver approved by requester)
```

**Impact**

A single admin user could unilaterally suppress security findings by requesting and immediately approving waivers. This removes the segregation-of-duties control intended to ensure that security exceptions receive independent review, and could allow findings to be hidden from compliance audits.

**Remediation Applied**

A `requested_by` field was added to the waiver model. The approve endpoint now compares `requested_by` against the current user's ID and rejects self-approval with HTTP 403. The four-eyes principle is now enforced at the application level.

**Verification**

Retest confirmed that self-approval returns `403 Forbidden` with the message "Cannot approve your own waiver request." Cross-user approval succeeds as expected.

---

### BL-03: Bulk Waive Endpoint -- Missing Authorization and Batch Limit

| Attribute              | Detail                                         |
| ---------------------- | ---------------------------------------------- |
| **Severity**           | MEDIUM                                         |
| **CVSS Score**         | 6.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N)      |
| **Status**             | **FIXED** -- verified March 19, 2026           |
| **OWASP Category**     | API1:2023 -- Broken Object Level Authorization |
| **Affected Component** | Bulk waive endpoint                            |

**Description**

The bulk waive endpoint allowed any authenticated user, including those with `viewer` role, to submit waiver requests for multiple findings simultaneously. Additionally, no batch size limit was enforced, enabling a single request to waive an arbitrary number of findings.

**Evidence**

```http
POST /api/v1/findings/bulk-waive HTTP/1.1
Authorization: Bearer <viewer_token>
Content-Type: application/json

{"finding_ids": ["uuid1", "uuid2", ..., "uuid500"], "reason": "Bulk false positive"}

Response: 200 OK  (all 500 findings waived)
```

**Impact**

A low-privilege viewer account could suppress large numbers of security findings without administrative authorization. Combined with automated scripting, this could be used to mass-dismiss findings before an audit or to obscure genuine security issues from dashboard reporting.

**Remediation Applied**

The endpoint now requires `AdminUser` authorization (admin role). A maximum batch size of 25 findings per request is enforced via Pydantic validation. Attempts to exceed the limit or access the endpoint as a viewer return appropriate error responses.

**Verification**

Retest confirmed: viewer tokens receive `403 Forbidden`, payloads exceeding 25 items receive `422 Unprocessable Entity`, and admin tokens with valid batch sizes succeed.

---

### BL-04: Refresh Token Race Condition

| Attribute              | Detail                                             |
| ---------------------- | -------------------------------------------------- |
| **Severity**           | MEDIUM                                             |
| **CVSS Score**         | 5.9 (AV:N/AC:H/PR:L/UI:N/S:U/C:H/I:N/A:N)          |
| **Status**             | **FIXED** -- verified March 19, 2026               |
| **OWASP Category**     | WSTG-SESS-06 -- Session Puzzling                   |
| **Affected Component** | `app/services/auth.py` -- `decode_refresh_token()` |

**Description**

When two concurrent HTTP requests presented the same refresh token to the `/auth/refresh` endpoint simultaneously, a time-of-check-to-time-of-use (TOCTOU) race condition allowed both requests to succeed. This resulted in two valid session pairs (access + refresh tokens) being issued from a single refresh token, violating the expected one-to-one rotation guarantee.

**Evidence**

Two simultaneous requests using the same refresh token:

```
Request A: POST /api/v1/auth/refresh  ->  200 OK (new token pair A)
Request B: POST /api/v1/auth/refresh  ->  200 OK (new token pair B)
```

Both token pairs were independently valid. The original refresh token was only revoked once.

**Impact**

An attacker who intercepted a single refresh token could race the legitimate client to produce a parallel session. While the window of exploitation is narrow (requires precise timing), successful exploitation yields persistent unauthorized access that survives the legitimate user's token rotation.

**Remediation Applied**

A `SELECT ... FOR UPDATE` clause was added to the refresh token lookup query in `decode_refresh_token()`. This acquires a row-level lock on the token record within the database transaction, serializing concurrent access. The second concurrent request now finds the token already revoked and fails with `401 Unauthorized`.

**Verification**

Retest using 10 concurrent refresh requests confirmed that exactly one request succeeds and all others receive `401 Unauthorized`.

---

### PT-01: Open Registration Without Email Verification

| Attribute              | Detail                                       |
| ---------------------- | -------------------------------------------- |
| **Severity**           | MEDIUM                                       |
| **CVSS Score**         | 5.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:L)    |
| **Status**             | **FIXED** -- verified March 19, 2026         |
| **OWASP Category**     | WSTG-IDNT-02 -- Account Provisioning Process |
| **Affected Component** | `POST /api/v1/auth/register`                 |

**Description**

The registration endpoint was publicly accessible without authentication, allowing anyone to create a new tenant and admin account. While rate limiting (5 registrations per hour) provided some mitigation, no email verification step was required. An attacker could create tenants with arbitrary email addresses, polluting the tenant namespace and potentially using the platform for reconnaissance or abuse.

**Remediation Applied**

The registration endpoint now requires a valid authenticated session (invitation-only model). New tenants are provisioned by existing administrators through the admin panel. The `CurrentUser` dependency was added to the endpoint, ensuring only authenticated users can trigger tenant creation.

**Verification**

Unauthenticated requests to `/api/v1/auth/register` now return `401 Unauthorized`.

---

### PT-02: TRACE Method Returns 500 Instead of 405

| Attribute              | Detail                                    |
| ---------------------- | ----------------------------------------- |
| **Severity**           | LOW                                       |
| **CVSS Score**         | 3.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **Status**             | Open                                      |
| **OWASP Category**     | WSTG-CONF-06 -- Test HTTP Methods         |
| **Affected Component** | Caddy reverse proxy / FastAPI             |

**Description**

Sending an HTTP TRACE request to the application returns a `500 Internal Server Error` response instead of the expected `405 Method Not Allowed`. While TRACE is effectively blocked (no request body is reflected), the 500 status code indicates unhandled exception processing, which could theoretically leak debugging information in certain configurations.

**Evidence**

```http
TRACE /api/v1/auth/login HTTP/1.1
Host: cspm.securekt.com

HTTP/1.1 500 Internal Server Error
Content-Type: application/json
{"detail": "Internal Server Error"}
```

**Impact**

Minimal. TRACE is not reflected and no sensitive data is disclosed. However, the 500 response may trigger false positives in automated vulnerability scanners and indicates that the HTTP method is not explicitly handled.

**Recommendation**

Configure Caddy or add FastAPI middleware to return `405 Method Not Allowed` for TRACE requests. Example Caddy configuration:

```
@trace method TRACE
respond @trace 405
```

---

### PT-03: Health Endpoint Discloses Component Names

| Attribute              | Detail                                    |
| ---------------------- | ----------------------------------------- |
| **Severity**           | LOW                                       |
| **CVSS Score**         | 3.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **Status**             | Open                                      |
| **OWASP Category**     | WSTG-INFO-02 -- Server Fingerprinting     |
| **Affected Component** | `GET /api/v1/health`                      |

**Description**

The health check endpoint returns a JSON response that includes the names and status of individual infrastructure components (e.g., `db`, `redis`). While this does not reveal version numbers or connection strings, it confirms the technology stack to an unauthenticated attacker.

**Evidence**

```http
GET /api/v1/health HTTP/1.1
Host: cspm.securekt.com

HTTP/1.1 200 OK
{"status": "healthy", "components": {"db": "up", "redis": "up"}}
```

**Impact**

Low. An attacker gains confirmation that the application uses PostgreSQL and Redis, which is also inferable from other signals. However, detailed component enumeration slightly reduces the attacker's reconnaissance effort.

**Recommendation**

Return only an aggregate status for unauthenticated requests (e.g., `{"status": "healthy"}`). Expose component-level detail only to authenticated admin users or restrict the endpoint to internal networks.

---

### PT-04: Metrics Endpoint Confirms Existence via 403

| Attribute              | Detail                                |
| ---------------------- | ------------------------------------- |
| **Severity**           | INFO                                  |
| **CVSS Score**         | N/A                                   |
| **Status**             | Accepted                              |
| **OWASP Category**     | WSTG-INFO-02 -- Server Fingerprinting |
| **Affected Component** | `GET /metrics`                        |

**Description**

The `/metrics` endpoint returns `403 Forbidden` rather than `404 Not Found`, confirming that a metrics collection system (likely Prometheus-compatible) is configured. While access is correctly denied, the 403 response leaks the existence of the endpoint.

**Recommendation**

Return `404 Not Found` for unauthenticated requests to the metrics endpoint, or restrict access at the reverse proxy level to internal monitoring IPs only.

---

### PT-05: Client Error Endpoint Accepts Unsanitized Input

| Attribute              | Detail                           |
| ---------------------- | -------------------------------- |
| **Severity**           | INFO                             |
| **CVSS Score**         | N/A                              |
| **Status**             | Accepted                         |
| **OWASP Category**     | WSTG-INPV-01 -- Input Validation |
| **Affected Component** | Client error reporting endpoint  |

**Description**

The client-side error reporting endpoint accepts arbitrary payloads without input validation or sanitization. While this does not result in server-side code execution (errors are logged, not executed), an attacker could inject misleading log entries or fill log storage with crafted payloads.

**Recommendation**

Add Pydantic schema validation to the error reporting endpoint. Enforce maximum payload size (e.g., 4 KB), restrict field types, and sanitize string content before writing to logs.

---

### PT-06: Login Timing Variance

| Attribute              | Detail                              |
| ---------------------- | ----------------------------------- |
| **Severity**           | INFO                                |
| **CVSS Score**         | N/A                                 |
| **Status**             | Accepted                            |
| **OWASP Category**     | WSTG-ATHN-03 -- Account Enumeration |
| **Affected Component** | `POST /api/v1/auth/login`           |

**Description**

A statistically significant (though small) timing difference was observed between login attempts for valid and invalid email addresses. The application already performs a dummy bcrypt comparison when the user is not found (`_DUMMY_HASH` constant), which substantially narrows the timing gap. However, in high-precision measurements (1000+ samples), a residual variance of approximately 2--5ms was detectable, likely due to the additional database query for existing users.

**Impact**

Minimal in practice. The timing difference is below the threshold exploitable over a network with typical jitter. The dummy bcrypt comparison is the correct mitigation and brings the gap within acceptable tolerances for most threat models. Account lockout and rate limiting further reduce the risk.

**Recommendation**

No immediate action required. For environments requiring the highest assurance, consider adding artificial random jitter (0--10ms) to the login response, or restructuring the authentication flow to perform the database lookup and bcrypt comparison in fixed time regardless of user existence.

---

## 7. Positive Security Controls

The PostureOne platform implements a comprehensive set of security controls that reflect security-conscious design and development practices. The following controls were verified during testing.

### 7.1 Transport Layer Security

| Control                      | Status | Detail                                                             |
| ---------------------------- | ------ | ------------------------------------------------------------------ |
| TLS 1.2+ enforced            | PASS   | TLS 1.3 active; TLS 1.0 and 1.1 connection attempts are rejected   |
| HSTS header                  | PASS   | `Strict-Transport-Security: max-age=31536000; includeSubDomains`   |
| Valid certificate            | PASS   | Let's Encrypt certificate with automatic renewal via Caddy         |
| No server version disclosure | PASS   | Server header does not reveal Caddy, Python, or framework versions |

### 7.2 HTTP Security Headers

| Header                  | Value                                                           | Status |
| ----------------------- | --------------------------------------------------------------- | ------ |
| Content-Security-Policy | `default-src 'self'; script-src 'self'; frame-ancestors 'none'` | PASS   |
| X-Frame-Options         | `DENY`                                                          | PASS   |
| X-Content-Type-Options  | `nosniff`                                                       | PASS   |
| Referrer-Policy         | `strict-origin-when-cross-origin`                               | PASS   |
| Permissions-Policy      | `camera=(), microphone=(), geolocation=()`                      | PASS   |
| CORS                    | Origin restricted to `cspm.securekt.com` only                   | PASS   |

### 7.3 Authentication and Session Management

| Control                       | Status | Detail                                                                                                                |
| ----------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------- |
| JWT algorithm pinning         | PASS   | `alg: none` tokens rejected; only HS256 accepted via `algorithms=[settings.jwt_algorithm]`                            |
| JWT signature validation      | PASS   | Tampered tokens (modified claims, truncated signature) rejected                                                       |
| JWT type enforcement          | PASS   | Token type field (`access`, `refresh`, `mfa_pending`, `password_reset`) validated on every decode; cross-use rejected |
| Refresh token rotation        | PASS   | Old token revoked on rotation; new pair issued                                                                        |
| Refresh token race protection | PASS   | `SELECT FOR UPDATE` prevents concurrent token reuse (post-fix)                                                        |
| Cookie security               | PASS   | `HttpOnly`, `Secure`, `SameSite=Lax` on both access and refresh cookies                                               |
| Refresh cookie path scoping   | PASS   | Refresh token cookie scoped to `/api/v1/auth` path only                                                               |
| Access token lifetime         | PASS   | 15-minute expiry                                                                                                      |
| Session idle timeout          | PASS   | 2-hour idle timeout enforced via `last_used_at` tracking on refresh tokens                                            |
| Session absolute timeout      | PASS   | 24-hour maximum session duration                                                                                      |
| Account lockout               | PASS   | 5 failed attempts triggers 15-minute lockout                                                                          |
| Timing oracle prevention      | PASS   | Dummy bcrypt hash comparison for nonexistent and locked accounts                                                      |
| Rate limiting (login)         | PASS   | 10 attempts per minute per IP                                                                                         |
| Rate limiting (registration)  | PASS   | 5 attempts per hour per IP                                                                                            |
| X-Forwarded-For bypass        | PASS   | Trusted proxy enforcement; spoofed headers from untrusted IPs ignored                                                 |
| MFA (TOTP)                    | PASS   | Standard TOTP with backup codes; brute-force protection (5 attempts per token via Redis)                              |
| MFA fail-closed               | PASS   | Redis outage during MFA check returns 503 (denies access) rather than bypassing verification                          |
| Password policy               | PASS   | zxcvbn score >= 3 required; real-time strength meter on frontend                                                      |
| Password reset                | PASS   | Time-limited token (1 hour); all existing sessions revoked on reset                                                   |

### 7.4 Authorization and Multi-Tenancy

| Control                   | Status | Detail                                                                                    |
| ------------------------- | ------ | ----------------------------------------------------------------------------------------- |
| Tenant isolation          | PASS   | Every query filtered by `effective_tenant_id`; cross-tenant requests return 404 (not 403) |
| RBAC enforcement          | PASS   | Viewer role blocked from 7 tested admin-only operations                                   |
| Self-privilege escalation | PASS   | Users cannot modify their own role                                                        |
| IDOR protection           | PASS   | Random UUIDs return 404 across all tested endpoints                                       |
| SCIM authentication       | PASS   | SCIM endpoints require separate SCIM token; standard JWT tokens rejected                  |
| API key scopes            | PASS   | Read-only keys blocked from write operations (post-fix)                                   |

### 7.5 Input Validation and Injection Prevention

| Control            | Status | Detail                                                                                                                                                                             |
| ------------------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQL injection      | PASS   | Pydantic validation + SQLAlchemy parameterized queries; tested on login, query params, path params                                                                                 |
| XSS (reflected)    | PASS   | JSON API responses with `Content-Type: application/json`; CSP blocks inline scripts                                                                                                |
| XSS (stored)       | PASS   | Input sanitized on output; CSP provides secondary defense                                                                                                                          |
| SSRF               | PASS   | AWS metadata (169.254.169.254), private IPs, localhost, IPv6 mapped addresses, DNS rebinding all blocked. SSO discovery URLs validated against allowlist of public HTTPS endpoints |
| Path traversal     | PASS   | Blocked; directory traversal sequences in URL paths and parameters rejected                                                                                                        |
| CRLF injection     | PASS   | Header injection attempts rejected                                                                                                                                                 |
| Host header attack | PASS   | Invalid Host headers rejected by Caddy                                                                                                                                             |

### 7.6 Cryptography and Data Protection

| Control                   | Status | Detail                                                                                                                                                   |
| ------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Passwords                 | PASS   | bcrypt with automatic salt generation                                                                                                                    |
| Credentials at rest       | PASS   | Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) for cloud credentials, webhook secrets, Slack URLs, MFA secrets, Jira tokens, SSO client secrets |
| Encryption key validation | PASS   | Application refuses to start without valid `CREDENTIAL_ENCRYPTION_KEY` in production mode                                                                |
| Secret key validation     | PASS   | Application refuses to start with default `secret_key` in production mode                                                                                |
| Backup code comparison    | PASS   | `hmac.compare_digest` for constant-time comparison (prevents timing attacks)                                                                             |

### 7.7 Operational Security

| Control                         | Status | Detail                                                                                          |
| ------------------------------- | ------ | ----------------------------------------------------------------------------------------------- |
| API docs disabled in production | PASS   | `/docs` and `/redoc` return 404 in production                                                   |
| Structured logging              | PASS   | JSON logging with `request_id`, `tenant_id`, `user_id` correlation fields                       |
| Audit logging                   | PASS   | Security-relevant operations (login, account changes, scans, waivers) logged with full context  |
| SSO error handling              | PASS   | Callback errors redirect with generic `?sso_error=auth_failed`; details logged server-side only |

---

## 8. Recommendations

The following recommendations are prioritized by impact and effort. Items are ordered from highest to lowest priority.

### Priority 1 -- Short Term (Next 30 Days)

| #    | Recommendation                                         | Effort | Rationale                                                                            |
| ---- | ------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------ |
| R-01 | Return 405 for TRACE requests                          | Low    | Eliminates scanner false positives and indicates proper HTTP method handling (PT-02) |
| R-02 | Restrict health endpoint detail to authenticated users | Low    | Reduce information disclosure without impacting monitoring (PT-03)                   |
| R-03 | Return 404 instead of 403 for `/metrics`               | Low    | Prevent endpoint enumeration (PT-04)                                                 |
| R-04 | Add schema validation to client error endpoint         | Low    | Prevent log injection and storage abuse (PT-05)                                      |

### Priority 2 -- Medium Term (Next 90 Days)

| #    | Recommendation                               | Effort | Rationale                                                                                            |
| ---- | -------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| R-05 | Implement API key audit logging              | Medium | Track API key usage patterns for anomaly detection; complements the scope enforcement fix in BL-01   |
| R-06 | Add waiver approval notification             | Medium | Notify the original requester when a waiver is approved or rejected; improves audit trail visibility |
| R-07 | Implement refresh token family detection     | Medium | If a revoked refresh token is reused, revoke all tokens in the family (detect token theft)           |
| R-08 | Add login jitter for timing oracle hardening | Low    | Add 0--10ms random delay to login responses for defense-in-depth against user enumeration (PT-06)    |

### Priority 3 -- Long Term (Next 6 Months)

| #    | Recommendation                                  | Effort | Rationale                                                                                           |
| ---- | ----------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------- |
| R-09 | Migrate to asymmetric JWT signing (RS256/ES256) | High   | Enables token verification without sharing the signing key; improves architecture for microservices |
| R-10 | Implement Content Security Policy reporting     | Medium | Add `report-uri` or `report-to` directive to detect CSP violations in production                    |
| R-11 | Conduct annual penetration test                 | --     | Establish recurring assessment cadence; retest all accepted findings                                |
| R-12 | Consider certificate transparency monitoring    | Low    | Detect unauthorized certificate issuance for `securekt.com` domains                                 |

---

## 9. Conclusion

The PostureOne CSPM platform demonstrates a **mature and well-considered security architecture**. The development team has implemented defense-in-depth across all critical layers: transport security, authentication, authorization, input validation, cryptography, and operational logging.

**Round 1** (Technical Penetration Test, score: **82/100**) revealed no critical or high-severity vulnerabilities. The application successfully defended against all tested injection attacks, authentication bypass attempts, and SSRF vectors. The findings were limited to low-severity information disclosure and hardening improvements.

**Round 2** (Business Logic Test, initial score: **52/100**, post-fix: **~85/100**) identified meaningful logic flaws in API key scope enforcement, waiver workflow integrity, and refresh token concurrency handling. These findings reflect the inherent complexity of business logic testing, where controls must enforce domain-specific rules that are not covered by generic security frameworks. The development team's rapid and thorough remediation of all four findings, including the critical API key scope bypass, demonstrates strong security responsiveness.

**Current Risk Posture:** The two remaining open findings (PT-02, PT-03) are low severity and carry minimal residual risk. The three informational items have been accepted as known risks with appropriate context. No critical, high, or medium-severity findings remain unresolved.

**Overall Assessment:** The PostureOne platform is **approved for production use** from a security perspective. The security controls in place exceed the baseline expectations for a SaaS CSPM product handling sensitive cloud security data. We recommend addressing the remaining low-severity items during normal development cycles and scheduling a follow-up assessment in 12 months.

---

## Appendix A -- Tools Used

| Tool                    | Version   | Purpose                                                    |
| ----------------------- | --------- | ---------------------------------------------------------- |
| Burp Suite Professional | 2025.12.1 | HTTP interception, request tampering, automated scanning   |
| Nuclei                  | 3.3.x     | Template-based vulnerability scanning                      |
| ffuf                    | 2.1.0     | Directory and endpoint fuzzing                             |
| sqlmap                  | 1.8.x     | SQL injection testing                                      |
| jwt_tool                | 2.2.7     | JWT algorithm confusion, tampering, and claim manipulation |
| testssl.sh              | 3.2       | TLS configuration analysis                                 |
| httpx (Go)              | 1.6.x     | Parallel HTTP probing                                      |
| curl                    | 8.7.x     | Manual HTTP request crafting                               |
| Python scripts          | 3.12      | Custom race condition and timing analysis scripts          |
| Postman                 | 11.x      | API workflow testing and collection management             |

## Appendix B -- Testing Credentials

Two test accounts were provisioned for the assessment:

| Account                       | Role   | Purpose                                              |
| ----------------------------- | ------ | ---------------------------------------------------- |
| `pentest-admin@securekt.com`  | Admin  | Full-privilege testing (RBAC, configuration, scans)  |
| `pentest-viewer@securekt.com` | Viewer | Low-privilege testing (RBAC enforcement, escalation) |
| API Key (read scope)          | --     | API key scope enforcement testing                    |
| API Key (write scope)         | --     | API key scope enforcement testing                    |

Test accounts were deactivated at the conclusion of the assessment.

---

_End of Report_

_Meridian Security Consulting -- MSC-2026-0147 -- CONFIDENTIAL_
