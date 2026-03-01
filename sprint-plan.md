# Sprint Plan — CSPM MVP (Azure → AWS)

> Target: SaaS multi-tenant | Team: 1 Backend (BE), 1 Frontend (FE), 1 Cloud/Sec (CS)
> Durata: 2 sprint × 2 settimane = 4 settimane totali

---

## Data Model Minimo

```
Tenant          1 ─── N  CloudAccount (Azure subscription / AWS account)
CloudAccount    1 ─── N  Asset
Asset           N ─── N  Finding (through asset_findings)
Finding         N ─── 1  Control
Finding         1 ─── N  Evidence
Finding         1 ─── 0..1  Remediation
Finding         1 ─── 0..1  Exception (waiver/SLA)
Control         N ─── 1  Framework (CIS-lite, custom)
```

| Entità           | Campi chiave                                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Tenant**       | id, name, slug, plan, created_at                                                                                                                                                     |
| **CloudAccount** | id, tenant_id, provider (azure\|aws), credential_ref, display_name, status, last_scan_at                                                                                             |
| **Asset**        | id, cloud_account_id, provider_id (ARM id / ARN), resource_type, name, region, tags (jsonb), raw_properties (jsonb), first_seen_at, last_seen_at                                     |
| **Control**      | id, code (es. CIS-AZ-01), name, description, severity (high\|medium\|low), framework_id, provider_check_ref (jsonb: {azure: "rec-id", aws: "rule-arn"})                              |
| **Finding**      | id, cloud_account_id, asset_id, control_id, status (pass\|fail\|error\|not_applicable), scan_id, first_detected_at, last_evaluated_at, dedup_key (unique: provider+resource+control) |
| **Evidence**     | id, finding_id, snapshot (jsonb), collected_at                                                                                                                                       |
| **Remediation**  | id, finding_id, description, status (open\|in_progress\|resolved\|accepted_risk), assigned_to, due_date                                                                              |
| **Exception**    | id, finding_id, reason, approved_by, expires_at, created_at                                                                                                                          |
| **Scan**         | id, cloud_account_id, scan_type (full\|incremental), status, started_at, finished_at, stats (jsonb)                                                                                  |

---

## Sprint 1 — Fondamenta + Azure Collector + Dashboard Base

**Obiettivo:** Connettere una subscription Azure, raccogliere inventory + secure score + recommendations, e visualizzare tutto in una dashboard funzionante.

**Definition of Done:**

- [ ] Un utente può registrarsi, creare un tenant e collegare una subscription Azure
- [ ] Lo scan raccoglie asset, secure score e recommendations via Resource Graph
- [ ] La dashboard mostra: score complessivo, lista asset, lista findings con severità
- [ ] Le API sono documentate (OpenAPI) e autenticate (JWT)
- [ ] Test: ≥70% coverage backend, integration test sulle API principali
- [ ] Docker Compose locale funzionante (app + db + redis)

### Week 1 — Setup + Collector Core

| #         | Story                                                                                                                                                                                             | Owner                                                                                                      | Size | Blocking?                        |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---- | -------------------------------- | --- |
| **S1-01** | **Project scaffold**: repo monorepo (backend FastAPI + frontend Next.js), Docker Compose (PostgreSQL, Redis), CI base (lint + test), Alembic init                                                 | BE                                                                                                         | M    | **Sì — blocca tutto**            |
| **S1-02** | **Data model + migrazioni**: creare tabelle Tenant, CloudAccount, Asset, Finding, Control, Evidence, Scan con Alembic                                                                             | BE                                                                                                         | M    | **Sì — blocca collector e API**  |
| **S1-03** | **Auth base**: registrazione, login, JWT access+refresh token, middleware tenant isolation (`effective_tenant_id`)                                                                                | BE                                                                                                         | M    | **Sì — blocca API tenant-aware** |
| **S1-04** | **Azure Collector — Inventory**: service che usa `azure-mgmt-resourcegraph` per query `Resources                                                                                                  | project id, name, type, location, tags`multi-subscription. Salva/aggiorna Asset con upsert su`provider_id` | CS   | L                                |     |
| **S1-05** | **Azure Collector — Secure Score**: fetch secure score aggregato via `Microsoft.Security/secureScores` REST API. Salvare come metadato del CloudAccount                                           | CS                                                                                                         | S    |                                  |
| **S1-06** | **Azure Collector — Recommendations**: fetch `Microsoft.Security/assessments` via Resource Graph query. Creare Finding per ogni recommendation, con status mapping (Healthy→pass, Unhealthy→fail) | CS                                                                                                         | L    |                                  |
| **S1-07** | **Design system + layout base**: shell app (sidebar, topbar, routing), theme, component library setup (shadcn/ui o simile)                                                                        | FE                                                                                                         | M    |                                  |

**Acceptance Criteria — Week 1:**

**S1-01** — Project scaffold

- `docker compose up` avvia tutti i servizi
- `pytest` e `pnpm test` passano (anche se con 0 test)
- Linter configurati (ruff, eslint) e CI green
- Struttura: `backend/app/{api,services,models,schemas}`, `frontend/src/{app,components,lib}`

**S1-02** — Data model

- Tutte le tabelle create con `alembic upgrade head`
- Foreign key e indici su: `asset.provider_id`, `finding.dedup_key` (unique), `finding.cloud_account_id+control_id`
- Modelli SQLAlchemy con relazioni definite

**S1-03** — Auth

- POST `/api/v1/auth/register` → crea tenant + user, ritorna JWT
- POST `/api/v1/auth/login` → ritorna access (15min) + refresh (7d)
- POST `/api/v1/auth/refresh` → rinnova access token
- Middleware: ogni request autenticata ha `request.state.tenant_id`
- Test: utente A non vede dati di utente B

**S1-04** — Inventory collector

- Dato un CloudAccount con credenziali Azure valide, raccoglie tutti i resource types
- Upsert: risorse nuove inserite, esistenti aggiornate, scomparse marcate `last_seen_at` invariato
- Gestisce paginazione Resource Graph (>1000 risultati)
- Logging strutturato (count risorse per tipo)
- Note tecniche: `azure-identity` DefaultAzureCredential, `azure-mgmt-resourcegraph` SDK, query KQL

**S1-05** — Secure Score

- Fetch score da `/providers/Microsoft.Security/secureScores/ascScore`
- Salvato in `cloud_account.metadata.secure_score` (jsonb)
- Gestisce 403/404 se Defender non attivo (log warning, non blocca scan)

**S1-06** — Recommendations

- Fetch assessments da Resource Graph: `securityresources | where type == "microsoft.security/assessments"`
- Mapping status: `Healthy` → pass, `Unhealthy/NotApplicable` → fail/not_applicable
- Dedup: `dedup_key = f"{provider}:{resource_id}:{assessment_name}"`
- Crea Finding + Evidence (snapshot della recommendation raw)

**S1-07** — Design system

- Layout responsive con sidebar collassabile
- Pagine stub: Dashboard, Assets, Findings, Settings
- Dark/light mode
- Loading states e empty states

---

### Week 2 — API + Dashboard + Scan Orchestration

| #         | Story                                                                                                                                                                           | Owner | Size | Blocking? |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---- | --------- |
| **S1-08** | **API CloudAccount CRUD**: `POST/GET/DELETE /api/v1/accounts` — registrare subscription Azure, validare credenziali con test connection                                         | BE    | M    |           |
| **S1-09** | **API Assets**: `GET /api/v1/assets` con filtri (type, region, account) + paginazione. `GET /api/v1/assets/{id}` con findings correlati                                         | BE    | S    |           |
| **S1-10** | **API Findings**: `GET /api/v1/findings` con filtri (severity, status, control, account) + paginazione. `GET /api/v1/findings/{id}` con evidence + asset                        | BE    | M    |           |
| **S1-11** | **API Dashboard summary**: `GET /api/v1/dashboard/summary` → secure score, conteggi per severità, top 5 failing controls, asset count per tipo                                  | BE    | S    |           |
| **S1-12** | **Scan orchestration**: `POST /api/v1/scans` avvia scan (Celery task o background task). Status polling `GET /api/v1/scans/{id}`. Sequenza: inventory → score → recommendations | CS    | M    |           |
| **S1-13** | **Dashboard page**: score card, donut chart severità, tabella top findings, barra risorse per tipo                                                                              | FE    | L    |           |
| **S1-14** | **Asset list page**: tabella con ricerca, filtri per tipo/regione, click → dettaglio asset con findings                                                                         | FE    | M    |           |
| **S1-15** | **Findings list page**: tabella con filtri severity/status, badge colorati, expand row per evidence                                                                             | FE    | M    |           |
| **S1-16** | **Settings page**: gestione cloud accounts (add/remove subscription), trigger scan manuale, status ultimo scan                                                                  | FE    | M    |           |

**Acceptance Criteria — Week 2:**

**S1-08** — CloudAccount API

- POST valida le credenziali Azure prima di salvare (test `ResourceGraphClient.resources()`)
- Credenziali salvate come riferimento (es. key vault ref o encrypted field), mai in chiaro
- DELETE soft-delete o cascade findings
- Response: `{ data: CloudAccount, error: null, meta: null }`

**S1-09/10** — Asset e Finding API

- Paginazione: `?page=1&size=20` → `meta: { total, page, size }`
- Filtri composabili via query params
- Ordinamento: `?sort=severity&order=desc`
- Include relazioni (finding.asset, finding.control) via `?include=asset,control`

**S1-11** — Dashboard summary

- Single query ottimizzata (evitare N+1)
- Cache Redis 5min (invalidata al termine scan)
- Response shape: `{ data: { secure_score, findings_by_severity, top_failing_controls, assets_by_type }, meta: { cached_at } }`

**S1-12** — Scan orchestration

- Scan idempotente: se scan in corso, ritorna 409 Conflict
- Status: `pending → running → completed | failed`
- Timeout: max 10 min per scan, abort se supera
- Stats finali: `{ assets_found, findings_created, findings_updated, duration_sec }`

**S1-13/14/15/16** — Pagine frontend

- Tutte le pagine chiamano API reali (no mock dopo sprint 1)
- Loading skeleton durante fetch
- Error state con retry
- Responsive (desktop-first, ma usabile su tablet)

---

## Sprint 2 — Normalizzazione + CIS-lite + Export + SLA/Waiver

**Obiettivo:** Dare significato ai findings con mapping CIS-lite, permettere export per audit, e gestire eccezioni/waiver.

**Definition of Done:**

- [ ] 20 controlli CIS-lite mappati e visibili in dashboard con drill-down per framework
- [ ] Export report in JSON + CSV + PDF evidence pack
- [ ] Sistema waiver/exception funzionante (richiesta, approvazione, scadenza)
- [ ] Findings normalizzati con severity uniforme e trend temporale
- [ ] RBAC base: ruoli admin/viewer per tenant
- [ ] Test: ≥80% coverage backend

### Week 3 — Normalizzazione + Framework + RBAC

| #         | Story                                                                                                                                                                                                 | Owner | Size | Blocking?                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---- | --------------------------- |
| **S2-01** | **Normalizer engine**: service che mappa recommendation Azure → Control interno. Configurazione mapping via YAML/JSON (provider_ref → control_code). Severity override se diversa dalla sorgente      | CS    | L    | **Sì — blocca CIS mapping** |
| **S2-02** | **CIS-lite seed**: creare 20 controlli ad alto segnale (IAM, logging, encryption, network, storage, key mgmt). Ogni control con: code, name, severity, remediation hint, provider_check_ref per Azure | CS    | M    |                             |
| **S2-03** | **RBAC**: ruoli `admin` e `viewer` per tenant. Admin: full CRUD + trigger scan + approve waiver. Viewer: read-only. Middleware permission check                                                       | BE    | M    |                             |
| **S2-04** | **Finding trend**: tabella `finding_history` o campo `status_changed_at`. API `GET /api/v1/dashboard/trend?period=30d` con serie temporale findings aperti per severity                               | BE    | M    |                             |
| **S2-05** | **Framework view UI**: pagina Compliance con lista controlli CIS-lite, % pass per controllo, drill-down per vedere findings associati                                                                 | FE    | L    |                             |
| **S2-06** | **Scan incrementale**: dopo il primo full scan, scan successivi confrontano solo delta (risorse nuove/modificate/rimosse). Riduce tempo scan e costi API                                              | CS    | M    |                             |

**Acceptance Criteria — Week 3:**

**S2-01** — Normalizer

- Mapping config in `backend/app/config/control_mappings.yaml`
- Formato: `{ azure_ref: "assessment-xxx", control_code: "CIS-AZ-01", severity_override: null }`
- Il normalizer gira come step post-collector nello scan pipeline
- Finding senza mapping → control_id null, flaggato come `unmapped` nei log

**S2-02** — CIS-lite seed

- 20 controlli coprenti: MFA (2), logging (3), encryption at rest (2), encryption in transit (2), storage public access (2), network (3), IAM (3), key management (3)
- Migration seed con `alembic upgrade` che inserisce i controlli
- Ogni controllo ha `provider_check_ref.azure` popolato

**S2-03** — RBAC

- Tabella `tenant_user` con campo `role` (enum: admin, viewer)
- Decorator `@require_role("admin")` sugli endpoint protetti
- Viewer che prova POST/DELETE riceve 403
- Test: viewer non può triggerare scan o approvare waiver

**S2-04** — Trend

- Query aggregata per giorno/settimana su `finding.first_detected_at` e `finding.last_evaluated_at`
- Response: `{ data: [{ date, high, medium, low }], meta: { period } }`
- Performance: query su indice `finding(cloud_account_id, last_evaluated_at)`

**S2-06** — Scan incrementale

- Primo scan: `scan_type=full`, scansiona tutto
- Scan successivi: `scan_type=incremental`, usa `last_scan_at` per filtrare
- Resource Graph: `| where properties.changedTime > datetime({last_scan})`
- Tempo scan incrementale < 30% del full scan (su dataset >500 risorse)

---

### Week 4 — Export + Waiver + Polish

| #         | Story                                                                                                                                                                                                         | Owner                                                                                                                    | Size | Blocking? |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---- | --------- | --- |
| **S2-07** | **Export JSON/CSV**: `GET /api/v1/export/findings?format=json                                                                                                                                                 | csv` con filtri. Include: asset, control, finding status, evidence summary. File generato async, download via signed URL | BE   | M         |     |
| **S2-08** | **Export PDF evidence pack**: report con executive summary (score, top findings) + dettaglio per controllo + evidence snapshot. Usa `weasyprint` o `reportlab`                                                | BE                                                                                                                       | L    |           |
| **S2-09** | **Exception/Waiver API**: `POST /api/v1/findings/{id}/exception` (request waiver). `PUT /api/v1/exceptions/{id}/approve` (admin approva). Exception ha `expires_at` — job giornaliero riapre findings scaduti | BE                                                                                                                       | M    |           |
| **S2-10** | **Exception UI**: bottone "Request Waiver" su finding, form con reason + expiry. Admin vede lista pending, può approvare/rifiutare. Badge "waived" su finding                                                 | FE                                                                                                                       | M    |           |
| **S2-11** | **Dashboard v2**: aggiungere trend chart (line chart 30d), compliance % per framework, filtro per cloud account. Migliorare card secure score con delta vs scan precedente                                    | FE                                                                                                                       | L    |           |
| **S2-12** | **Export UI**: pagina Reports con: seleziona filtri → genera report → download. History report generati                                                                                                       | FE                                                                                                                       | M    |           |
| **S2-13** | **User management UI**: invita utenti al tenant (email), assegna ruolo admin/viewer, rimuovi utente                                                                                                           | FE                                                                                                                       | M    |           |
| **S2-14** | **Scan scheduling**: cron job configurabile (es. ogni 24h). `PUT /api/v1/accounts/{id}/schedule` con cron expression. Celery beat o APScheduler                                                               | CS                                                                                                                       | M    |           |

**Acceptance Criteria — Week 4:**

**S2-07** — Export JSON/CSV

- CSV con header leggibili (non nomi tecnici)
- JSON segue schema documentato
- File >10k righe: generazione async + notifica "report pronto"
- Filtri: severity, status, control, date range

**S2-08** — PDF evidence pack

- Sezioni: Executive Summary → Score/Trend → Findings per Severity → Dettaglio per Control → Appendice Evidence
- Logo/branding placeholder (configurabile per tenant in futuro)
- Max 50 pagine (paginare findings se necessario)

**S2-09** — Exception/Waiver

- Exception lifecycle: `requested → approved | rejected → expired`
- Finding con exception approvata: status resta `fail` ma flag `waived=true`
- Job cron giornaliero: riapre exception scadute (set `waived=false`)
- Audit trail: chi ha richiesto, chi ha approvato, quando

**S2-14** — Scan scheduling

- Cron validato (no schedule < 1h)
- Se scan precedente ancora in corso, skip con log warning
- Dashboard mostra next scheduled scan

---

## Task Non-Funzionali (trasversali, entrambi gli sprint)

| #         | Task                                                                                                                         | Owner | Sprint | Size |
| --------- | ---------------------------------------------------------------------------------------------------------------------------- | ----- | ------ | ---- |
| **NF-01** | **Logging strutturato**: JSON logs con `request_id`, `tenant_id`, `user_id`. Correlazione tra request e background task      | BE    | 1      | S    |
| **NF-02** | **Rate limiting**: per tenant, 100 req/min API, 5 scan/ora. Risposta 429 con `Retry-After` header                            | BE    | 1      | S    |
| **NF-03** | **Audit log**: tabella `audit_events` — registra login, scan trigger, waiver approve/reject, export. Immutable (append-only) | BE    | 2      | M    |
| **NF-04** | **Health check + monitoring**: `GET /health` (db + redis + celery). Endpoint per Prometheus metrics (opzionale)              | BE    | 1      | S    |
| **NF-05** | **Credential management**: credenziali Azure criptate at rest (Fernet o simile). Rotate endpoint. Mai loggare credenziali    | CS    | 1      | M    |

---

## Rischi e Contromisure

| Rischio                                                              | Impatto                               | Contromisura                                                                                             |
| -------------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| **Azure API rate limiting** (Resource Graph: 15 req/5sec per tenant) | Scan fallisce o è lentissimo          | Batching query, backoff esponenziale, coda con priorità                                                  |
| **Defender for Cloud non attivo** sulla subscription                 | Nessun secure score / recommendations | Graceful degradation: inventario funziona, score mostra "N/A", log warning                               |
| **Multi-tenant data leak**                                           | Un tenant vede dati di un altro       | `effective_tenant_id` su ogni query, test automatici di isolamento, RLS PostgreSQL come layer aggiuntivo |
| **Scope creep** (troppi controlli, troppi provider)                  | MVP non chiude in 4 settimane         | CIS-lite fisso a 20 controlli, solo Azure in MVP, AWS è Sprint 3+                                        |
| **PDF generation lenta**                                             | Timeout su report grandi              | Generazione async con Celery, cache report per 1h                                                        |
| **Credenziali Azure scadute/revocate**                               | Scan fallisce silenziosamente         | Health check credenziali prima di ogni scan, notifica utente se fallisce                                 |

---

## Stack Tecnologico

| Layer        | Tecnologia                                                              |
| ------------ | ----------------------------------------------------------------------- |
| Backend      | Python 3.12, FastAPI, SQLAlchemy 2.x async, Pydantic v2, Celery + Redis |
| Frontend     | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts  |
| Database     | PostgreSQL 16, Alembic migrazioni                                       |
| Cache/Queue  | Redis 7                                                                 |
| Azure SDK    | `azure-identity`, `azure-mgmt-resourcegraph`, `azure-mgmt-security`     |
| Auth         | JWT (PyJWT), bcrypt password hashing                                    |
| Export       | `csv` stdlib, `weasyprint` (PDF)                                        |
| Infra locale | Docker Compose                                                          |
| CI           | GitHub Actions (lint + test + build)                                    |

---

## API Reference (endpoint principali)

```
# Auth
POST   /api/v1/auth/register          → crea tenant + user
POST   /api/v1/auth/login             → access + refresh token
POST   /api/v1/auth/refresh           → rinnova access token

# Cloud Accounts
POST   /api/v1/accounts               → collega subscription Azure
GET    /api/v1/accounts               → lista account del tenant
DELETE /api/v1/accounts/{id}          → rimuovi account
PUT    /api/v1/accounts/{id}/schedule → configura scan scheduling

# Scans
POST   /api/v1/scans                  → trigger scan manuale
GET    /api/v1/scans/{id}             → status scan

# Assets
GET    /api/v1/assets                 → lista con filtri + paginazione
GET    /api/v1/assets/{id}            → dettaglio + findings

# Findings
GET    /api/v1/findings               → lista con filtri + paginazione
GET    /api/v1/findings/{id}          → dettaglio + evidence

# Controls / Compliance
GET    /api/v1/controls               → lista controlli CIS-lite
GET    /api/v1/controls/{id}/findings → findings per controllo

# Dashboard
GET    /api/v1/dashboard/summary      → score, conteggi, top findings
GET    /api/v1/dashboard/trend        → serie temporale 30d

# Exceptions / Waiver
POST   /api/v1/findings/{id}/exception    → richiedi waiver
PUT    /api/v1/exceptions/{id}/approve    → approva (admin)
PUT    /api/v1/exceptions/{id}/reject     → rifiuta (admin)

# Export
GET    /api/v1/export/findings        → JSON/CSV
POST   /api/v1/export/report          → genera PDF evidence pack
GET    /api/v1/export/report/{id}     → download report
```

---

## Schermate Dashboard (UX reference)

### 1. Overview Dashboard

- **Score card**: secure score numerico + trend arrow (↑↓)
- **Donut chart**: findings per severity (High rosso, Medium arancio, Low giallo, Pass verde)
- **Bar chart**: asset count per resource type (top 10)
- **Tabella**: top 10 failing controls con % fail e count asset impattati
- **Status bar**: ultimo scan (data, durata, risultato), prossimo scan schedulato

### 2. Compliance View

- **Progress bar** per framework (CIS-lite): X/20 controlli passed
- **Lista controlli**: accordion con nome, severity, % pass, count findings
- **Expand**: mostra findings associati con link a asset
- **Filtri**: severity, status (pass/fail/waived), search

### 3. Finding Detail

- **Header**: control name + severity badge + status
- **Asset info**: nome, tipo, regione, subscription
- **Evidence**: JSON viewer con snapshot raw
- **Remediation**: istruzioni + link documentazione
- **Actions**: Request Waiver, Mark as Resolved
- **Timeline**: history (detected → evaluated → waived → reopened)
