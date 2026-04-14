#!/usr/bin/env bash
# =============================================================================
# CSPM Lab Environment — Azure Free Tier Resources
# =============================================================================
#
# Provisions Azure resources with MIXED security postures (secure + insecure)
# so that the CSPM scanner produces varied and interesting findings.
#
# Usage:
#   bash infra/azure-free-tier.sh              # Provision all resources
#   bash infra/azure-free-tier.sh --cleanup    # Delete the resource group
#   bash infra/azure-free-tier.sh --dry-run    # Show what would be created
#
# Requirements:
#   - Azure CLI (az) installed and logged in
#   - Azure Free Tier subscription
#   - openssl (for random suffix generation)
#
# Cost: All resources use Azure Free Tier quotas. Estimated cost: $0/month
#   - B1s VM: 750 hrs/month free (12 months)
#   - App Service F1: always free
#   - Cosmos DB free tier: 1000 RU/s, 25 GB
#   - SQL Database free offer: 100K vCore seconds/month
#   - Log Analytics: 5 GB/month free
#   - Storage: 5 GB LRS free (12 months)
#   - Key Vault: 10K operations free
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Color output helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; }
section() { echo -e "\n${BOLD}${CYAN}=== $* ===${NC}\n"; }

# ---------------------------------------------------------------------------
# Configurable variables
# ---------------------------------------------------------------------------
RESOURCE_GROUP="${CSPM_LAB_RG:-cspm-lab-rg}"
LOCATION="${CSPM_LAB_LOCATION:-westeurope}"
ADMIN_EMAIL="${CSPM_LAB_EMAIL:-admin@example.com}"
SUFFIX="${CSPM_LAB_SUFFIX:-$(openssl rand -hex 3)}"

# Derived names (must be globally unique where required)
STORAGE_SECURE="cspmlabsec${SUFFIX}"
STORAGE_INSECURE="cspmlabins${SUFFIX}"
KEYVAULT_NAME="cspm-lab-kv-${SUFFIX}"
NSG_SECURE="cspm-lab-nsg-secure"
NSG_INSECURE="cspm-lab-nsg-insecure"
VNET_NAME="cspm-lab-vnet"
SUBNET_NAME="default"
VM_NAME="cspm-lab-vm"
APPSERVICE_PLAN="cspm-lab-plan"
WEBAPP_SECURE="cspm-lab-app-sec-${SUFFIX}"
WEBAPP_INSECURE="cspm-lab-app-insec-${SUFFIX}"
SQL_SERVER="cspm-lab-sql-${SUFFIX}"
SQL_DB="cspmlab-db"
COSMOS_ACCOUNT="cspm-lab-cosmos-${SUFFIX}"
LOG_ANALYTICS="cspm-lab-logs"
ACTION_GROUP_NAME="cspm-lab-ag"
ALERT_NAME="cspm-lab-security-policy-alert"

# SSH key for VM (generate ephemeral if not provided)
SSH_KEY_PATH="${CSPM_LAB_SSH_KEY:-${HOME}/.ssh/cspm-lab-key}"

# ---------------------------------------------------------------------------
# Cleanup mode
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--cleanup" ]]; then
    section "Cleanup: Deleting resource group ${RESOURCE_GROUP}"
    warn "This will permanently delete ALL resources in ${RESOURCE_GROUP}."
    read -r -p "Are you sure? (yes/no): " confirm
    if [[ "${confirm}" == "yes" ]]; then
        az group delete --name "${RESOURCE_GROUP}" --yes --no-wait
        ok "Resource group deletion initiated (running in background)."
        info "Run 'az group show -n ${RESOURCE_GROUP}' to check status."
    else
        info "Cleanup cancelled."
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    section "DRY RUN — No resources will be created"
fi

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
section "Checking prerequisites"

if ! command -v az &>/dev/null; then
    fail "Azure CLI (az) is not installed. Install from https://aka.ms/installazurecli"
    exit 1
fi
ok "Azure CLI found: $(az version --query '\"azure-cli\"' -o tsv 2>/dev/null || echo 'unknown')"

# Verify login
if ! az account show &>/dev/null; then
    fail "Not logged in to Azure. Run 'az login' first."
    exit 1
fi

ACCOUNT_NAME=$(az account show --query 'name' -o tsv)
SUBSCRIPTION_ID=$(az account show --query 'id' -o tsv)
CURRENT_USER_ID=$(az ad signed-in-user show --query 'id' -o tsv 2>/dev/null || echo "")
CURRENT_USER_UPN=$(az ad signed-in-user show --query 'userPrincipalName' -o tsv 2>/dev/null || echo "")
ok "Logged in to subscription: ${ACCOUNT_NAME} (${SUBSCRIPTION_ID})"
if [[ -n "${CURRENT_USER_UPN}" ]]; then
    ok "Current user: ${CURRENT_USER_UPN}"
fi

info "Resource Group:  ${RESOURCE_GROUP}"
info "Location:        ${LOCATION}"
info "Suffix:          ${SUFFIX}"
info "Admin Email:     ${ADMIN_EMAIL}"
echo ""

if [[ "${DRY_RUN}" == true ]]; then
    info "Resources that would be created:"
    echo "  - Resource Group: ${RESOURCE_GROUP}"
    echo "  - Storage (secure): ${STORAGE_SECURE}"
    echo "  - Storage (insecure): ${STORAGE_INSECURE}"
    echo "  - Key Vault: ${KEYVAULT_NAME}"
    echo "  - NSG (secure): ${NSG_SECURE}"
    echo "  - NSG (insecure): ${NSG_INSECURE}"
    echo "  - VNet: ${VNET_NAME}"
    echo "  - VM: ${VM_NAME} (Standard_B1s)"
    echo "  - App Service Plan: ${APPSERVICE_PLAN} (F1)"
    echo "  - Web App (secure): ${WEBAPP_SECURE}"
    echo "  - Web App (insecure): ${WEBAPP_INSECURE}"
    echo "  - SQL Server: ${SQL_SERVER}"
    echo "  - SQL Database: ${SQL_DB}"
    echo "  - Cosmos DB: ${COSMOS_ACCOUNT}"
    echo "  - Log Analytics: ${LOG_ANALYTICS}"
    echo "  - Activity Log Alert: ${ALERT_NAME}"
    exit 0
fi

# Track timing
START_TIME=$(date +%s)

# ============================================================================
# 1. RESOURCE GROUP
# ============================================================================
section "1. Resource Group"

if az group show --name "${RESOURCE_GROUP}" &>/dev/null; then
    warn "Resource group '${RESOURCE_GROUP}' already exists — reusing."
else
    az group create \
        --name "${RESOURCE_GROUP}" \
        --location "${LOCATION}" \
        --output none
    ok "Created resource group '${RESOURCE_GROUP}' in ${LOCATION}."
fi

# ============================================================================
# 2. STORAGE ACCOUNTS (2 — one secure, one insecure)
# ============================================================================
section "2. Storage Accounts"

# --- 2a. Secure storage account ---
# Expected CSPM results:
#   PASS: CIS-AZ-09 (HTTPS only)
#   PASS: CIS-AZ-11 (public access disabled)
#   PASS: CIS-AZ-12 (no public containers)
#   PASS: CIS-AZ-72 (TLS 1.2)
#   PASS: CIS-AZ-74 (shared key disabled)
#   FAIL: CIS-AZ-07 (no CMK — would need Key Vault CMK, not free)
#   FAIL: CIS-AZ-15 (network ACL default Allow — no VNet service endpoint on free tier)
#   FAIL: CIS-AZ-73 (no infrastructure encryption — must be set at creation)
#   FAIL: CIS-AZ-75 (blob versioning — not set here)
info "Creating secure storage account: ${STORAGE_SECURE}"
az storage account create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${STORAGE_SECURE}" \
    --location "${LOCATION}" \
    --sku "Standard_LRS" \
    --kind "StorageV2" \
    --min-tls-version "TLS1_2" \
    --https-only true \
    --allow-blob-public-access false \
    --allow-shared-key-access false \
    --require-infrastructure-encryption true \
    --output none
ok "Secure storage account created: ${STORAGE_SECURE}"

# Enable blob soft delete (data protection)
az storage account blob-service-properties update \
    --resource-group "${RESOURCE_GROUP}" \
    --account-name "${STORAGE_SECURE}" \
    --enable-delete-retention true \
    --delete-retention-days 7 \
    --enable-container-delete-retention true \
    --container-delete-retention-days 7 \
    --enable-versioning true \
    --output none
ok "  Blob soft delete + versioning enabled."

# --- 2b. Insecure storage account ---
# Expected CSPM results:
#   PASS: CIS-AZ-09 (HTTPS only — still enforced)
#   FAIL: CIS-AZ-11 (public access enabled)
#   FAIL: CIS-AZ-12 (public containers possible)
#   FAIL: CIS-AZ-72 (TLS 1.0)
#   FAIL: CIS-AZ-74 (shared key allowed)
#   FAIL: CIS-AZ-07 (no CMK)
#   FAIL: CIS-AZ-15 (network unrestricted)
#   FAIL: CIS-AZ-73 (no infra encryption)
#   FAIL: CIS-AZ-75 (no blob versioning)
info "Creating insecure storage account: ${STORAGE_INSECURE}"
az storage account create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${STORAGE_INSECURE}" \
    --location "${LOCATION}" \
    --sku "Standard_LRS" \
    --kind "StorageV2" \
    --min-tls-version "TLS1_0" \
    --https-only true \
    --allow-blob-public-access true \
    --allow-shared-key-access true \
    --output none
ok "Insecure storage account created: ${STORAGE_INSECURE}"
warn "  Deliberately insecure: TLS 1.0, public blob access, shared key enabled."

# ============================================================================
# 3. KEY VAULT
# ============================================================================
section "3. Key Vault"

# Expected CSPM results:
#   PASS: CIS-AZ-16 (purge protection enabled)
#   PASS: CIS-AZ-17 (soft delete enabled — default since 2020)
#   PASS: CIS-AZ-21 (network ACL default deny)
#   PASS: CIS-AZ-22 (RBAC authorization enabled)
#   FAIL: CIS-AZ-78 (no private endpoint — free tier limitation)
#   Keys: one PASS (CIS-AZ-18, has expiry), one FAIL (no expiry)
info "Creating Key Vault: ${KEYVAULT_NAME}"
az keyvault create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${KEYVAULT_NAME}" \
    --location "${LOCATION}" \
    --enable-purge-protection true \
    --enable-rbac-authorization true \
    --default-action "Deny" \
    --sku "standard" \
    --output none
ok "Key Vault created: ${KEYVAULT_NAME}"

# Assign Key Vault Crypto Officer role to current user so we can create keys
if [[ -n "${CURRENT_USER_ID}" ]]; then
    KEYVAULT_ID=$(az keyvault show --name "${KEYVAULT_NAME}" --query 'id' -o tsv)
    info "Assigning Key Vault Crypto Officer role to current user..."
    az role assignment create \
        --role "Key Vault Crypto Officer" \
        --assignee "${CURRENT_USER_ID}" \
        --scope "${KEYVAULT_ID}" \
        --output none 2>/dev/null || warn "Role assignment may already exist."

    # Also assign Key Vault Secrets Officer for secret creation
    az role assignment create \
        --role "Key Vault Secrets Officer" \
        --assignee "${CURRENT_USER_ID}" \
        --scope "${KEYVAULT_ID}" \
        --output none 2>/dev/null || warn "Role assignment may already exist."

    # Wait for RBAC propagation
    info "Waiting 30s for RBAC propagation..."
    sleep 30

    # Create key WITH expiration (PASS for CIS-AZ-18)
    EXPIRY_DATE=$(date -u -v+1y "+%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d "+1 year" "+%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "2027-03-04T00:00:00Z")
    info "Creating key with expiration: cspm-lab-key-secure (expires ${EXPIRY_DATE})"
    az keyvault key create \
        --vault-name "${KEYVAULT_NAME}" \
        --name "cspm-lab-key-secure" \
        --kty "RSA" \
        --size 2048 \
        --expires "${EXPIRY_DATE}" \
        --output none 2>/dev/null && ok "  Key 'cspm-lab-key-secure' created with expiration." \
        || warn "  Could not create key (RBAC may still be propagating — try manually later)."

    # Create key WITHOUT expiration (FAIL for CIS-AZ-18)
    info "Creating key without expiration: cspm-lab-key-insecure (no expiry)"
    az keyvault key create \
        --vault-name "${KEYVAULT_NAME}" \
        --name "cspm-lab-key-insecure" \
        --kty "RSA" \
        --size 2048 \
        --output none 2>/dev/null && ok "  Key 'cspm-lab-key-insecure' created WITHOUT expiration." \
        || warn "  Could not create key (RBAC may still be propagating — try manually later)."

    # Create secret WITH expiration (PASS for CIS-AZ-76)
    info "Creating secret with expiration: cspm-lab-secret-secure"
    az keyvault secret set \
        --vault-name "${KEYVAULT_NAME}" \
        --name "cspm-lab-secret-secure" \
        --value "test-secret-value-secure" \
        --expires "${EXPIRY_DATE}" \
        --output none 2>/dev/null && ok "  Secret 'cspm-lab-secret-secure' created with expiration." \
        || warn "  Could not create secret."

    # Create secret WITHOUT expiration (FAIL for CIS-AZ-76)
    info "Creating secret without expiration: cspm-lab-secret-insecure"
    az keyvault secret set \
        --vault-name "${KEYVAULT_NAME}" \
        --name "cspm-lab-secret-insecure" \
        --value "test-secret-value-insecure" \
        --output none 2>/dev/null && ok "  Secret 'cspm-lab-secret-insecure' created WITHOUT expiration." \
        || warn "  Could not create secret."
else
    warn "Cannot determine current user — skipping key/secret creation."
    warn "Create keys manually after assigning RBAC roles."
fi

# ============================================================================
# 4. NETWORK SECURITY GROUPS (2 — one secure, one insecure)
# ============================================================================
section "4. Network Security Groups"

# --- 4a. Secure NSG ---
# Expected CSPM results:
#   PASS: CIS-AZ-13 (no SSH from internet)
#   PASS: CIS-AZ-14 (no RDP from internet)
#   FAIL: CIS-AZ-06 (no flow logs — requires Network Watcher + storage, best-effort check)
info "Creating secure NSG: ${NSG_SECURE}"
az network nsg create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${NSG_SECURE}" \
    --location "${LOCATION}" \
    --output none
ok "Secure NSG created: ${NSG_SECURE}"
info "  No open SSH/RDP rules — only default Azure rules."

# --- 4b. Insecure NSG ---
# Expected CSPM results:
#   FAIL: CIS-AZ-13 (SSH open from 0.0.0.0/0)
#   FAIL: CIS-AZ-14 (RDP open from 0.0.0.0/0)
#   FAIL: CIS-AZ-06 (no flow logs)
info "Creating insecure NSG: ${NSG_INSECURE}"
az network nsg create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${NSG_INSECURE}" \
    --location "${LOCATION}" \
    --output none

# SSH from anywhere (FAIL CIS-AZ-13)
az network nsg rule create \
    --resource-group "${RESOURCE_GROUP}" \
    --nsg-name "${NSG_INSECURE}" \
    --name "Allow-SSH-From-Internet" \
    --priority 100 \
    --direction "Inbound" \
    --access "Allow" \
    --protocol "Tcp" \
    --source-address-prefixes "0.0.0.0/0" \
    --source-port-ranges "*" \
    --destination-address-prefixes "*" \
    --destination-port-ranges "22" \
    --output none

# RDP from anywhere (FAIL CIS-AZ-14)
az network nsg rule create \
    --resource-group "${RESOURCE_GROUP}" \
    --nsg-name "${NSG_INSECURE}" \
    --name "Allow-RDP-From-Internet" \
    --priority 110 \
    --direction "Inbound" \
    --access "Allow" \
    --protocol "Tcp" \
    --source-address-prefixes "0.0.0.0/0" \
    --source-port-ranges "*" \
    --destination-address-prefixes "*" \
    --destination-port-ranges "3389" \
    --output none

ok "Insecure NSG created: ${NSG_INSECURE}"
warn "  Deliberately insecure: SSH (22) and RDP (3389) open from 0.0.0.0/0."

# ============================================================================
# 5. VIRTUAL NETWORK + SUBNET
# ============================================================================
section "5. Virtual Network + Subnet"

# Expected CSPM results:
#   FAIL: CIS-AZ-46 (no DDoS protection plan — paid service)
info "Creating VNet: ${VNET_NAME} (10.0.0.0/16)"
az network vnet create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${VNET_NAME}" \
    --location "${LOCATION}" \
    --address-prefix "10.0.0.0/16" \
    --subnet-name "${SUBNET_NAME}" \
    --subnet-prefix "10.0.0.0/24" \
    --output none
ok "VNet created: ${VNET_NAME} with subnet ${SUBNET_NAME}"

# Attach secure NSG to subnet
info "Attaching secure NSG to subnet..."
az network vnet subnet update \
    --resource-group "${RESOURCE_GROUP}" \
    --vnet-name "${VNET_NAME}" \
    --name "${SUBNET_NAME}" \
    --network-security-group "${NSG_SECURE}" \
    --output none
ok "  Secure NSG attached to subnet '${SUBNET_NAME}'."

# ============================================================================
# 6. VIRTUAL MACHINE (B1s — Free Tier)
# ============================================================================
section "6. Virtual Machine (Standard_B1s)"

# Expected CSPM results:
#   PASS: CIS-AZ-31 (managed disks — default)
#   PASS: CIS-AZ-33 (boot diagnostics enabled)
#   FAIL: CIS-AZ-32 (no disk encryption — ADE requires Key Vault Premium)
#   FAIL: CIS-AZ-34 (no secure boot — B1s may not support trusted launch)
#   FAIL: CIS-AZ-65 (NIC has public IP — needed for SSH access in lab)
#   PASS: CIS-AZ-66 (IP forwarding disabled — default)

# Generate SSH key if it does not exist
if [[ ! -f "${SSH_KEY_PATH}" ]]; then
    info "Generating SSH key at ${SSH_KEY_PATH}..."
    ssh-keygen -t rsa -b 4096 -f "${SSH_KEY_PATH}" -N "" -q
    ok "  SSH key generated."
else
    info "Using existing SSH key: ${SSH_KEY_PATH}"
fi

info "Creating VM: ${VM_NAME} (Standard_B1s, Ubuntu 22.04)"
az vm create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${VM_NAME}" \
    --location "${LOCATION}" \
    --size "Standard_B1s" \
    --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest" \
    --admin-username "cspmadmin" \
    --ssh-key-value "${SSH_KEY_PATH}.pub" \
    --authentication-type "ssh" \
    --vnet-name "${VNET_NAME}" \
    --subnet "${SUBNET_NAME}" \
    --nsg "" \
    --public-ip-address "${VM_NAME}-pip" \
    --os-disk-size-gb 30 \
    --boot-diagnostics-storage "" \
    --output none

# Enable boot diagnostics with managed storage (PASS CIS-AZ-33)
az vm boot-diagnostics enable \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${VM_NAME}" \
    --output none 2>/dev/null || warn "Boot diagnostics may already be enabled."

ok "VM created: ${VM_NAME} (Standard_B1s, SSH key auth, boot diagnostics on)"
info "  Public IP for lab SSH access (FAIL CIS-AZ-65 — intentional for lab)."

# ============================================================================
# 7. APP SERVICE (F1 Free Tier — 2 apps, mixed posture)
# ============================================================================
section "7. App Service (F1 Free Tier)"

# Create shared App Service Plan (F1 Free)
info "Creating App Service Plan: ${APPSERVICE_PLAN} (F1 Free)"
az appservice plan create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${APPSERVICE_PLAN}" \
    --location "${LOCATION}" \
    --sku "F1" \
    --is-linux \
    --output none
ok "App Service Plan created: ${APPSERVICE_PLAN} (F1 Free, Linux)"

# --- 7a. Secure Web App ---
# Expected CSPM results:
#   PASS: CIS-AZ-10 (HTTPS only)
#   PASS: CIS-AZ-23 (TLS 1.2)
#   PASS: CIS-AZ-24 (remote debugging off)
#   PASS: CIS-AZ-25 (FTP disabled)
#   PASS: CIS-AZ-26 (managed identity)
#   FAIL: CIS-AZ-67 (client cert — not enabled, optional in lab)
#   FAIL: CIS-AZ-68 (Always On — not available on F1 Free)
#   FAIL: CIS-AZ-69 (HTTP/2 — set below)
#   FAIL: CIS-AZ-70 (VNet integration — not available on F1)
#   FAIL: CIS-AZ-71 (auth not configured)
info "Creating secure web app: ${WEBAPP_SECURE}"
az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APPSERVICE_PLAN}" \
    --name "${WEBAPP_SECURE}" \
    --runtime "NODE:20-lts" \
    --output none

# Apply secure configuration
az webapp update \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${WEBAPP_SECURE}" \
    --https-only true \
    --output none

az webapp config set \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${WEBAPP_SECURE}" \
    --min-tls-version "1.2" \
    --remote-debugging-enabled false \
    --ftps-state "Disabled" \
    --http20-enabled true \
    --output none

# Enable system-assigned managed identity (PASS CIS-AZ-26)
az webapp identity assign \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${WEBAPP_SECURE}" \
    --output none

ok "Secure web app created: ${WEBAPP_SECURE}"
info "  HTTPS only, TLS 1.2, no FTP, no remote debug, managed identity, HTTP/2."

# --- 7b. Insecure Web App ---
# Expected CSPM results:
#   PASS: CIS-AZ-10 (HTTPS only — still enforced)
#   FAIL: CIS-AZ-23 (TLS 1.0)
#   FAIL: CIS-AZ-24 (remote debugging ON)
#   FAIL: CIS-AZ-25 (FTP enabled — AllAllowed)
#   FAIL: CIS-AZ-26 (no managed identity)
#   FAIL: CIS-AZ-67 (no client cert)
#   FAIL: CIS-AZ-68 (no Always On — F1)
#   FAIL: CIS-AZ-69 (no HTTP/2)
#   FAIL: CIS-AZ-70 (no VNet integration)
#   FAIL: CIS-AZ-71 (no auth)
info "Creating insecure web app: ${WEBAPP_INSECURE}"
az webapp create \
    --resource-group "${RESOURCE_GROUP}" \
    --plan "${APPSERVICE_PLAN}" \
    --name "${WEBAPP_INSECURE}" \
    --runtime "NODE:20-lts" \
    --output none

# Apply insecure configuration
az webapp update \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${WEBAPP_INSECURE}" \
    --https-only true \
    --output none

az webapp config set \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${WEBAPP_INSECURE}" \
    --min-tls-version "1.0" \
    --remote-debugging-enabled true \
    --ftps-state "AllAllowed" \
    --http20-enabled false \
    --output none

ok "Insecure web app created: ${WEBAPP_INSECURE}"
warn "  Deliberately insecure: TLS 1.0, remote debugging ON, FTP enabled, no identity."

# ============================================================================
# 8. SQL SERVER + DATABASE (Free Offer)
# ============================================================================
section "8. SQL Server + Database"

# Expected CSPM results:
#   PASS: CIS-AZ-27 (public access disabled)
#   PASS: CIS-AZ-28 (TLS 1.2)
#   PASS/FAIL: CIS-AZ-29 (AAD admin — configured if current user available)
#   FAIL: CIS-AZ-30 (auditing — best-effort, may not detect via Resource Graph)
#   PASS: CIS-AZ-08 (TDE — enabled by default on Azure SQL)

# Generate a random password for SQL admin (required even with AAD)
SQL_ADMIN_PASSWORD="CspmLab-$(openssl rand -hex 8)!"

info "Creating SQL Server: ${SQL_SERVER}"
az sql server create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${SQL_SERVER}" \
    --location "${LOCATION}" \
    --admin-user "cspmadmin" \
    --admin-password "${SQL_ADMIN_PASSWORD}" \
    --minimal-tls-version "1.2" \
    --enable-public-network-access false \
    --output none
ok "SQL Server created: ${SQL_SERVER} (TLS 1.2, public access disabled)"

# Set AAD admin if we have the current user info (PASS CIS-AZ-29)
if [[ -n "${CURRENT_USER_UPN}" && -n "${CURRENT_USER_ID}" ]]; then
    info "Setting Azure AD administrator..."
    az sql server ad-admin create \
        --resource-group "${RESOURCE_GROUP}" \
        --server-name "${SQL_SERVER}" \
        --display-name "${CURRENT_USER_UPN}" \
        --object-id "${CURRENT_USER_ID}" \
        --output none 2>/dev/null && ok "  AAD admin configured: ${CURRENT_USER_UPN}" \
        || warn "  Could not set AAD admin."
fi

# Create database using free offer SKU
info "Creating SQL Database: ${SQL_DB} (free offer)"
az sql db create \
    --resource-group "${RESOURCE_GROUP}" \
    --server "${SQL_SERVER}" \
    --name "${SQL_DB}" \
    --edition "GeneralPurpose" \
    --compute-model "Serverless" \
    --family "Gen5" \
    --capacity 1 \
    --use-free-limit \
    --free-limit-exhaustion-behavior "AutoPause" \
    --output none
ok "SQL Database created: ${SQL_DB} (free tier, TDE enabled by default)"

# Enable auditing to the secure storage account (PASS CIS-AZ-30)
info "Enabling SQL Server auditing..."
STORAGE_KEY=$(az storage account keys list \
    --resource-group "${RESOURCE_GROUP}" \
    --account-name "${STORAGE_SECURE}" \
    --query '[0].value' -o tsv 2>/dev/null || echo "")
if [[ -n "${STORAGE_KEY}" ]]; then
    # For RBAC-only storage, we need a different approach.
    # Since the secure storage has shared key disabled, use the insecure one for audit logs.
    AUDIT_STORAGE_KEY=$(az storage account keys list \
        --resource-group "${RESOURCE_GROUP}" \
        --account-name "${STORAGE_INSECURE}" \
        --query '[0].value' -o tsv 2>/dev/null || echo "")
    if [[ -n "${AUDIT_STORAGE_KEY}" ]]; then
        AUDIT_STORAGE_ENDPOINT=$(az storage account show \
            --resource-group "${RESOURCE_GROUP}" \
            --name "${STORAGE_INSECURE}" \
            --query 'primaryEndpoints.blob' -o tsv)
        az sql server audit-policy update \
            --resource-group "${RESOURCE_GROUP}" \
            --name "${SQL_SERVER}" \
            --state "Enabled" \
            --storage-account "${STORAGE_INSECURE}" \
            --storage-key "${AUDIT_STORAGE_KEY}" \
            --storage-endpoint "${AUDIT_STORAGE_ENDPOINT}" \
            --output none 2>/dev/null && ok "  SQL auditing enabled." \
            || warn "  Could not enable SQL auditing."
    fi
else
    warn "  Could not retrieve storage key — skipping SQL auditing setup."
fi

# ============================================================================
# 9. COSMOS DB (Free Tier)
# ============================================================================
section "9. Cosmos DB (Free Tier)"

# Expected CSPM results:
#   PASS: CIS-AZ-35 (public access disabled)
#   PASS: CIS-AZ-36 (VNet filter enabled)
#   FAIL: CIS-AZ-81 (no CMK — requires Key Vault Premium)
#   FAIL: CIS-AZ-82 (no automatic failover — single region in free tier)
info "Creating Cosmos DB account: ${COSMOS_ACCOUNT} (this takes 3-5 minutes...)"
az cosmosdb create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${COSMOS_ACCOUNT}" \
    --locations regionName="${LOCATION}" failoverPriority=0 isZoneRedundant=false \
    --enable-free-tier true \
    --kind "GlobalDocumentDB" \
    --default-consistency-level "Session" \
    --enable-public-network false \
    --enable-virtual-network true \
    --output none
ok "Cosmos DB account created: ${COSMOS_ACCOUNT}"
info "  Free tier, public access disabled, VNet filter enabled."
info "  No CMK, no automatic failover (expected FAILs)."

# ============================================================================
# 10. LOG ANALYTICS WORKSPACE (Free Tier — 5GB/month)
# ============================================================================
section "10. Log Analytics Workspace"

# Expected CSPM results:
#   FAIL: CIS-AZ-61 (retention 30 days < 90 days required)
#   FAIL: CIS-AZ-62 (no CMK encryption)
info "Creating Log Analytics workspace: ${LOG_ANALYTICS}"
az monitor log-analytics workspace create \
    --resource-group "${RESOURCE_GROUP}" \
    --workspace-name "${LOG_ANALYTICS}" \
    --location "${LOCATION}" \
    --retention-time 30 \
    --output none
ok "Log Analytics workspace created: ${LOG_ANALYTICS} (30-day retention, free tier)"
warn "  30-day retention will FAIL CIS-AZ-61 (requires >= 90 days)."
warn "  No CMK encryption will FAIL CIS-AZ-62."

# ============================================================================
# 11. ACTIVITY LOG ALERT
# ============================================================================
section "11. Activity Log Alert"

# Expected CSPM results:
#   PASS: CIS-AZ-05 (alert for security policy changes)

# Create action group first
info "Creating action group: ${ACTION_GROUP_NAME}"
az monitor action-group create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${ACTION_GROUP_NAME}" \
    --short-name "cspm-ag" \
    --action email "admin-email" "${ADMIN_EMAIL}" \
    --output none
ok "Action group created: ${ACTION_GROUP_NAME}"

# Create activity log alert for security policy changes (PASS CIS-AZ-05)
ACTION_GROUP_ID=$(az monitor action-group show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${ACTION_GROUP_NAME}" \
    --query 'id' -o tsv)

info "Creating activity log alert: ${ALERT_NAME}"
az monitor activity-log alert create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${ALERT_NAME}" \
    --description "Alert on security policy changes (CIS-AZ-05)" \
    --condition category=Security \
                and operationName=Microsoft.Security/policies/write \
    --action-group "${ACTION_GROUP_ID}" \
    --output none
ok "Activity log alert created: ${ALERT_NAME}"
info "  Monitors: Microsoft.Security/policies/write operations."

# ============================================================================
# SUMMARY
# ============================================================================
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
MINUTES=$(( ELAPSED / 60 ))
SECONDS_REMAINING=$(( ELAPSED % 60 ))

section "Provisioning Complete"
echo ""
info "Total time: ${MINUTES}m ${SECONDS_REMAINING}s"
info "Resource group: ${RESOURCE_GROUP} (${LOCATION})"
info "Suffix used: ${SUFFIX}"
echo ""

# Print summary table
echo -e "${BOLD}${CYAN}CSPM Lab Resources — Expected Scan Results${NC}"
echo ""
printf "${BOLD}%-35s %-30s %-8s %-s${NC}\n" "RESOURCE" "TYPE" "RESULT" "CHECKS"
printf "%-35s %-30s %-8s %-s\n" "-----------------------------------" "------------------------------" "--------" "---------------------"

# Storage Secure
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${STORAGE_SECURE}" "Storage Account" "MIXED" "PASS: 09,11,12,72,74,75"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 04,07,15,73"

# Storage Insecure
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${STORAGE_INSECURE}" "Storage Account" "MIXED" "PASS: 09"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 04,07,11,12,15,72,73,74,75"

# Key Vault
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${KEYVAULT_NAME}" "Key Vault" "MIXED" "PASS: 16,17,21,22"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 78"

# Key Vault Keys
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "  cspm-lab-key-secure" "KV Key" "PASS" "PASS: 18"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "  cspm-lab-key-insecure" "KV Key" "FAIL" "FAIL: 18"

# Key Vault Secrets
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "  cspm-lab-secret-secure" "KV Secret" "PASS" "PASS: 76"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "  cspm-lab-secret-insecure" "KV Secret" "FAIL" "FAIL: 76"

# NSG Secure
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${NSG_SECURE}" "NSG" "MIXED" "PASS: 13,14"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 06"

# NSG Insecure
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "${NSG_INSECURE}" "NSG" "FAIL" "FAIL: 06,13,14"

# VNet
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "${VNET_NAME}" "Virtual Network" "FAIL" "FAIL: 46"

# VM
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${VM_NAME}" "Virtual Machine" "MIXED" "PASS: 31,33,66"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 32,34,65"

# Web App Secure
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${WEBAPP_SECURE}" "App Service" "MIXED" "PASS: 10,23,24,25,26,69"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 67,68,70,71"

# Web App Insecure
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${WEBAPP_INSECURE}" "App Service" "MIXED" "PASS: 10"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 23,24,25,26,67,68,69,70,71"

# SQL Server
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${SQL_SERVER}" "SQL Server" "MIXED" "PASS: 27,28,29"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 30 (best-effort)"

# SQL Database
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${SQL_DB}" "SQL Database" "PASS" "PASS: 08 (TDE default)"

# Cosmos DB
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${COSMOS_ACCOUNT}" "Cosmos DB" "MIXED" "PASS: 35,36"
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "" "" "" "FAIL: 81,82"

# Log Analytics
printf "%-35s %-30s ${RED}%-8s${NC} %-s\n" "${LOG_ANALYTICS}" "Log Analytics" "FAIL" "FAIL: 61,62"

# Activity Log Alert
printf "%-35s %-30s ${GREEN}%-8s${NC} %-s\n" "${ALERT_NAME}" "Activity Log Alert" "PASS" "PASS: 05"

echo ""
echo -e "${BOLD}Check coverage summary:${NC}"
echo -e "  Total CIS controls covered:      ${BOLD}~35${NC} of 84"
echo -e "  Expected PASS findings:           ${GREEN}~25${NC}"
echo -e "  Expected FAIL findings:           ${RED}~40${NC}"
echo -e "  Resource types provisioned:       ${BOLD}11${NC} (storage, keyvault, nsg, vnet, vm, webapp, sql, cosmosdb, log-analytics, activity-alert, managed-disk)"
echo ""
echo -e "${BOLD}Checks NOT covered (require non-free resources):${NC}"
echo -e "  CIS-AZ-01,02:  MFA (Defender for Cloud)"
echo -e "  CIS-AZ-03:     RBAC roles (read-only detection)"
echo -e "  CIS-AZ-19,20:  VM endpoint protection / updates (Defender)"
echo -e "  CIS-AZ-37,38:  PostgreSQL flexible server (not free)"
echo -e "  CIS-AZ-39,40:  Container Registry (Basic SKU not free)"
echo -e "  CIS-AZ-41-44:  AKS / App Gateway (not free)"
echo -e "  CIS-AZ-45:     Public IP DDoS (Standard tier)"
echo -e "  CIS-AZ-47-50:  Network Watcher, VPN GW, Front Door"
echo -e "  CIS-AZ-51-56:  MySQL, Redis Cache (not free)"
echo -e "  CIS-AZ-57-60:  Event Hub, Service Bus (not free)"
echo -e "  CIS-AZ-79,80:  Batch account (not free)"
echo -e "  CIS-AZ-83,84:  AKS extended (not free)"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo -e "  1. Register this Azure subscription in the CSPM tool"
echo -e "  2. Use Reader + Security Reader roles for the CSPM service principal"
echo -e "  3. Run a scan to see the mixed security posture findings"
echo -e "  4. When done: ${YELLOW}bash infra/azure-free-tier.sh --cleanup${NC}"
echo ""
echo -e "${GREEN}Done.${NC}"
