"""IaC remediation snippets for CIS Azure controls.

Maps control codes to Terraform, Bicep, and Azure CLI fix suggestions.

Snippets use `@@placeholder@@` markers that `render_for_asset()`
substitutes with values extracted from the finding's asset ARM ID
(see `app.utils.arm_id.parse_provider_id`). Supported placeholders:

    @@name@@              leaf resource name (e.g. "myapp-prod")
    @@resource_group@@    resource group name (e.g. "rg-prod")
    @@subscription_id@@   full subscription GUID
    @@resource_type@@     leaf resource type (e.g. "sites")
    @@provider@@          provider namespace (e.g. "Microsoft.Web")
    @@full_type@@         "Microsoft.Web/sites"

We use `@@...@@` (not `{...}` or `$...`) because HCL and Bicep both
make heavy use of `{}` and `${}`, and Python's standard formatters
(`str.format`, `string.Template`) would clash or escape-burden the
source of this file. Simple `str.replace()` over the marker set is
unambiguous, readable, and zero-escape.

When a snippet cannot be rendered for an asset (missing ARM ID, parse
failure) the un-rendered template is returned so the UI still shows a
copy-paste starting point with the `@@placeholder@@` markers visible.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.asset import Asset

logger = logging.getLogger(__name__)

REMEDIATION_SNIPPETS: dict[str, dict[str, str]] = {
    # ── Storage ──────────────────────────────────────────────────────────
    "CIS-AZ-07": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                     = "@@name@@"
  resource_group_name      = "@@resource_group@@"
  location                 = "@@location@@"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.example.id]
  }

  customer_managed_key {
    key_vault_key_id          = azurerm_key_vault_key.example.id
    user_assigned_identity_id = azurerm_user_assigned_identity.example.id
  }
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    encryption: {
      keySource: 'Microsoft.Keyvault'
      keyvaultproperties: {
        keyname: keyVaultKey.name
        keyvaulturi: keyVault.properties.vaultUri
      }
      identity: {
        userAssignedIdentity: managedIdentity.id
      }
    }
  }
}""",
        "azure_cli": (
            "az storage account update --name @@name@@ --resource-group @@resource_group@@"
            " --encryption-key-source Microsoft.Keyvault"
            " --encryption-key-vault @@vault_uri@@ --encryption-key-name @@key_name@@"
        ),
        "description": ("Enable customer-managed key (CMK) encryption for the storage account using a Key Vault key."),
    },
    "CIS-AZ-09": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                      = "@@name@@"
  resource_group_name       = "@@resource_group@@"
  location                  = "@@location@@"
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enforce HTTPS-only access
  https_traffic_only_enabled = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
  }
}""",
        "azure_cli": "az storage account update --name @@name@@ --resource-group @@resource_group@@ --https-only true",
        "description": "Enforce HTTPS-only access (secure transfer) on the storage account.",
    },
    "CIS-AZ-11": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                      = "@@name@@"
  resource_group_name       = "@@resource_group@@"
  location                  = "@@location@@"
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Disable anonymous blob public access
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
  }
}""",
        "azure_cli": (
            "az storage account update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --allow-blob-public-access false"
        ),
        "description": "Disable blob public access on the storage account to prevent anonymous reads.",
    },
    "CIS-AZ-72": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                      = "@@name@@"
  resource_group_name       = "@@resource_group@@"
  location                  = "@@location@@"
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enforce minimum TLS 1.2
  min_tls_version = "TLS1_2"
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
  }
}""",
        "azure_cli": (
            "az storage account update --name @@name@@ --resource-group @@resource_group@@ --min-tls-version TLS1_2"
        ),
        "description": "Set the minimum TLS version to 1.2 on the storage account.",
    },
    "CIS-AZ-73": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                      = "@@name@@"
  resource_group_name       = "@@resource_group@@"
  location                  = "@@location@@"
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enable infrastructure (double) encryption
  infrastructure_encryption_enabled = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    encryption: {
      requireInfrastructureEncryption: true
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
    }
  }
}""",
        "azure_cli": (
            "# Infrastructure encryption must be enabled at storage"
            " account creation time.\n"
            "# It cannot be toggled after creation."
            " Recreate the account with:\n"
            "az storage account create --name @@name@@"
            " --resource-group @@resource_group@@ --location @@location@@"
            " --sku Standard_LRS"
            " --require-infrastructure-encryption true"
        ),
        "description": (
            "Enable infrastructure encryption (double encryption)"
            " on the storage account."
            " Note: this must be set at creation time."
        ),
    },
    # ── NSG / Network ───────────────────────────────────────────────────
    "CIS-AZ-06": {
        "terraform": """resource "azurerm_network_watcher_flow_log" "@@tf_name@@" {
  name                 = "nsg-flow-log"
  network_watcher_name = azurerm_network_watcher.example.name
  resource_group_name  = "@@resource_group@@"

  network_security_group_id = azurerm_network_security_group.example.id
  storage_account_id        = azurerm_storage_account.logs.id
  enabled                   = true
  version                   = 2

  retention_policy {
    enabled = true
    days    = 90
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = azurerm_log_analytics_workspace.example.workspace_id
    workspace_region      = azurerm_log_analytics_workspace.example.location
    workspace_resource_id = azurerm_log_analytics_workspace.example.id
    interval_in_minutes   = 10
  }
}""",
        "bicep": """resource flowLog 'Microsoft.Network/networkWatchers/flowLogs@2023-04-01' = {
  name: '${networkWatcher.name}/nsg-flow-log'
  location: resourceGroup().location
  properties: {
    targetResourceId: nsg.id
    storageId: storageAccount.id
    enabled: true
    format: {
      type: 'JSON'
      version: 2
    }
    retentionPolicy: {
      days: 90
      enabled: true
    }
    flowAnalyticsConfiguration: {
      networkWatcherFlowAnalyticsConfiguration: {
        enabled: true
        workspaceResourceId: logAnalytics.id
        trafficAnalyticsInterval: 10
      }
    }
  }
}""",
        "azure_cli": (
            "az network watcher flow-log create --name @@flow_log_name@@"
            " --nsg @@nsg_id@@ --resource-group @@resource_group@@"
            " --storage-account @@storage_id@@ --enabled true"
            " --retention 90 --workspace @@workspace_id@@"
        ),
        "description": "Enable NSG flow logs with retention and traffic analytics for network monitoring.",
    },
    "CIS-AZ-13": {
        "terraform": """resource "azurerm_network_security_rule" "deny_ssh_internet" {
  name                        = "DenySSHFromInternet"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = "@@resource_group@@"
  network_security_group_name = azurerm_network_security_group.example.name
}""",
        "bicep": """resource nsgRule 'Microsoft.Network/networkSecurityGroups/securityRules@2023-04-01' = {
  name: '${nsg.name}/DenySSHFromInternet'
  properties: {
    priority: 100
    direction: 'Inbound'
    access: 'Deny'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRange: '22'
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}""",
        "azure_cli": (
            "az network nsg rule create --resource-group @@resource_group@@"
            " --nsg-name @@name@@ --name DenySSHFromInternet"
            " --priority 100 --direction Inbound --access Deny"
            " --protocol Tcp --destination-port-ranges 22"
            " --source-address-prefixes Internet"
        ),
        "description": "Deny inbound SSH (port 22) from the internet by adding a high-priority deny rule to the NSG.",
    },
    "CIS-AZ-14": {
        "terraform": """resource "azurerm_network_security_rule" "deny_rdp_internet" {
  name                        = "DenyRDPFromInternet"
  priority                    = 101
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "3389"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = "@@resource_group@@"
  network_security_group_name = azurerm_network_security_group.example.name
}""",
        "bicep": """resource nsgRule 'Microsoft.Network/networkSecurityGroups/securityRules@2023-04-01' = {
  name: '${nsg.name}/DenyRDPFromInternet'
  properties: {
    priority: 101
    direction: 'Inbound'
    access: 'Deny'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRange: '3389'
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}""",
        "azure_cli": (
            "az network nsg rule create --resource-group @@resource_group@@"
            " --nsg-name @@name@@ --name DenyRDPFromInternet"
            " --priority 101 --direction Inbound --access Deny"
            " --protocol Tcp --destination-port-ranges 3389"
            " --source-address-prefixes Internet"
        ),
        "description": "Deny inbound RDP (port 3389) from the internet by adding a high-priority deny rule to the NSG.",
    },
    # ── Web App / App Service ───────────────────────────────────────────
    "CIS-AZ-10": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  # Enforce HTTPS only
  https_only = true

  site_config {}
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {}
  }
}""",
        "azure_cli": "az webapp update --name @@name@@ --resource-group @@resource_group@@ --set httpsOnly=true",
        "description": "Enforce HTTPS-only access on the web app to redirect all HTTP traffic to HTTPS.",
    },
    "CIS-AZ-23": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    # Enforce minimum TLS 1.2
    minimum_tls_version = "1.2"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      minTlsVersion: '1.2'
    }
  }
}""",
        "azure_cli": "az webapp config set --name @@name@@ --resource-group @@resource_group@@ --min-tls-version 1.2",
        "description": "Set the minimum TLS version to 1.2 for the web app.",
    },
    "CIS-AZ-25": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    # Disable FTP entirely (or use "FtpsOnly" for FTPS)
    ftps_state = "Disabled"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      ftpsState: 'Disabled'
    }
  }
}""",
        "azure_cli": "az webapp config set --name @@name@@ --resource-group @@resource_group@@ --ftps-state Disabled",
        "description": "Disable FTP on the web app. Use 'FtpsOnly' if FTPS is needed, or 'Disabled' to block all FTP.",
    },
    # ── Key Vault ───────────────────────────────────────────────────────
    "CIS-AZ-16": {
        "terraform": """resource "azurerm_key_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable purge protection (irreversible once enabled)
  purge_protection_enabled = true
  soft_delete_retention_days = 90
}""",
        "bicep": """resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enablePurgeProtection: true
    softDeleteRetentionInDays: 90
  }
}""",
        "azure_cli": (
            "az keyvault update --name @@name@@ --resource-group @@resource_group@@ --enable-purge-protection true"
        ),
        "description": (
            "Enable purge protection on the Key Vault."
            " This is irreversible once enabled and prevents"
            " permanent deletion during the retention period."
        ),
    },
    "CIS-AZ-17": {
        "terraform": """resource "azurerm_key_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Soft delete is enabled by default since 2020-12-15
  # Explicitly set retention period
  soft_delete_retention_days = 90
}""",
        "bicep": """resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
  }
}""",
        "azure_cli": (
            "# Soft delete is enforced by default on new"
            " Key Vaults.\n"
            "# For older vaults, enable it:\n"
            "az keyvault update --name @@name@@"
            " --resource-group @@resource_group@@ --enable-soft-delete true"
        ),
        "description": (
            "Enable soft delete on the Key Vault to allow recovery of deleted keys, secrets, and certificates."
        ),
    },
    "CIS-AZ-21": {
        "terraform": """resource "azurerm_key_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Restrict network access
  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"

    # Allow specific VNets
    virtual_network_subnet_ids = [
      azurerm_subnet.example.id,
    ]

    # Allow specific IPs (optional)
    ip_rules = ["203.0.113.0/24"]
  }
}""",
        "bicep": """resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      virtualNetworkRules: [
        { id: subnet.id }
      ]
      ipRules: [
        { value: '203.0.113.0/24' }
      ]
    }
  }
}""",
        "azure_cli": (
            "az keyvault update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --default-action Deny --bypass AzureServices"
        ),
        "description": (
            "Restrict Key Vault network access by setting the"
            " default firewall action to Deny and allowing"
            " only specific VNets/IPs."
        ),
    },
    # ── SQL Server ──────────────────────────────────────────────────────
    "CIS-AZ-27": {
        "terraform": """resource "azurerm_mssql_server" "@@tf_name@@" {
  name                         = "@@name@@"
  resource_group_name          = "@@resource_group@@"
  location                     = "@@location@@"
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = var.sql_admin_password

  # Disable public network access
  public_network_access_enabled = false
}

# Use private endpoint instead
resource "azurerm_private_endpoint" "sql" {
  name                = "pe-sql"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "sql-connection"
    private_connection_resource_id = azurerm_mssql_server.example.id
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }
}""",
        "bicep": """resource sqlServer 'Microsoft.Sql/servers@2023-02-01-preview' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    publicNetworkAccess: 'Disabled'
    version: '12.0'
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = {
  name: 'pe-sql'
  location: resourceGroup().location
  properties: {
    subnet: { id: subnet.id }
    privateLinkServiceConnections: [
      {
        name: 'sql-connection'
        properties: {
          privateLinkServiceId: sqlServer.id
          groupIds: ['sqlServer']
        }
      }
    ]
  }
}""",
        "azure_cli": (
            "az sql server update --name @@name@@ --resource-group @@resource_group@@ --enable-public-network false"
        ),
        "description": ("Disable public network access on the SQL Server and use private endpoints for connectivity."),
    },
    "CIS-AZ-28": {
        "terraform": """resource "azurerm_mssql_server" "@@tf_name@@" {
  name                         = "@@name@@"
  resource_group_name          = "@@resource_group@@"
  location                     = "@@location@@"
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = var.sql_admin_password

  # Enforce minimum TLS 1.2
  minimum_tls_version = "1.2"
}""",
        "bicep": """resource sqlServer 'Microsoft.Sql/servers@2023-02-01-preview' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    version: '12.0'
  }
}""",
        "azure_cli": (
            "az sql server update --name @@name@@ --resource-group @@resource_group@@ --minimal-tls-version 1.2"
        ),
        "description": "Set the minimum TLS version to 1.2 on the SQL Server.",
    },
    # ── Cosmos DB ───────────────────────────────────────────────────────
    "CIS-AZ-35": {
        "terraform": """resource "azurerm_cosmosdb_account" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Disable public network access
  public_network_access_enabled = false

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = "@@location@@"
    failover_priority = 0
  }
}""",
        "bicep": """resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'GlobalDocumentDB'
  properties: {
    publicNetworkAccess: 'Disabled'
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: resourceGroup().location
        failoverPriority: 0
      }
    ]
  }
}""",
        "azure_cli": (
            "az cosmosdb update --name @@name@@ --resource-group @@resource_group@@ --enable-public-network false"
        ),
        "description": ("Disable public network access on the Cosmos DB account and use private endpoints."),
    },
    # ── ACR ─────────────────────────────────────────────────────────────
    "CIS-AZ-39": {
        "terraform": """resource "azurerm_container_registry" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  sku                 = "Standard"

  # Disable admin user -- use Azure AD service principal instead
  admin_enabled = false
}""",
        "bicep": """resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'Standard' }
  properties: {
    adminUserEnabled: false
  }
}""",
        "azure_cli": "az acr update --name @@name@@ --resource-group @@resource_group@@ --admin-enabled false",
        "description": (
            "Disable the admin user on the container registry."
            " Use Azure AD service principals or managed"
            " identity for authentication."
        ),
    },
    # ── AKS ─────────────────────────────────────────────────────────────
    "CIS-AZ-41": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  # Enable Kubernetes RBAC
  role_based_access_control_enabled = true

  # Also enable Azure AD integration for RBAC
  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    managed            = true
  }

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_D2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}""",
        "bicep": """resource aksCluster 'Microsoft.ContainerService/managedClusters@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: 'example'
    enableRBAC: true
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }
    agentPoolProfiles: [
      {
        name: 'default'
        count: 1
        vmSize: 'Standard_D2_v2'
        mode: 'System'
      }
    ]
  }
}""",
        "azure_cli": (
            "# RBAC cannot be enabled on an existing"
            " non-RBAC cluster.\n"
            "# For new clusters:\n"
            "az aks create --name @@name@@"
            " --resource-group @@resource_group@@"
            " --enable-rbac --enable-aad --enable-azure-rbac"
        ),
        "description": (
            "Enable Kubernetes RBAC on the AKS cluster with Azure AD integration for centralized access control."
        ),
    },
    "CIS-AZ-42": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  # Configure network policy
  network_profile {
    network_plugin = "azure"
    network_policy = "calico"  # or "azure"
  }

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_D2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}""",
        "bicep": """resource aksCluster 'Microsoft.ContainerService/managedClusters@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: 'example'
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'calico'
    }
    agentPoolProfiles: [
      {
        name: 'default'
        count: 1
        vmSize: 'Standard_D2_v2'
        mode: 'System'
      }
    ]
  }
}""",
        "azure_cli": (
            "# Network policy must be set at cluster"
            " creation time:\n"
            "az aks create --name @@name@@"
            " --resource-group @@resource_group@@"
            " --network-plugin azure --network-policy calico"
        ),
        "description": (
            "Configure a network policy engine (Azure or Calico) on the AKS cluster to control pod-to-pod traffic."
        ),
    },
    # ── Storage soft delete (blob) ──────────────────────────────────────
    "CIS-AZ-75": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                     = "@@name@@"
  resource_group_name      = "@@resource_group@@"
  location                 = "@@location@@"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  blob_properties {
    # Enable blob versioning
    versioning_enabled = true

    # Enable soft delete for blobs
    delete_retention_policy {
      days = 30
    }

    # Enable soft delete for containers
    container_delete_retention_policy {
      days = 30
    }
  }
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: {
      enabled: true
      days: 30
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 30
    }
  }
}""",
        "azure_cli": (
            "az storage account blob-service-properties update"
            " --account-name @@name@@ --resource-group @@resource_group@@"
            " --enable-versioning true"
            " --enable-delete-retention true"
            " --delete-retention-days 30"
            " --enable-container-delete-retention true"
            " --container-delete-retention-days 30"
        ),
        "description": "Enable blob versioning and soft delete to protect against accidental deletion.",
    },
    # ── Additional high-value controls ──────────────────────────────────
    "CIS-AZ-15": {
        "terraform": """resource "azurerm_storage_account_network_rules" "@@tf_name@@" {
  storage_account_id = azurerm_storage_account.example.id

  default_action = "Deny"
  bypass         = ["AzureServices"]

  virtual_network_subnet_ids = [
    azurerm_subnet.example.id,
  ]

  ip_rules = ["203.0.113.0/24"]
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      virtualNetworkRules: [
        { id: subnet.id, action: 'Allow' }
      ]
      ipRules: [
        { value: '203.0.113.0/24', action: 'Allow' }
      ]
    }
  }
}""",
        "azure_cli": (
            "az storage account update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --default-action Deny --bypass AzureServices"
        ),
        "description": "Restrict storage account network access to specific VNets and IP ranges.",
    },
    "CIS-AZ-37": {
        "terraform": """resource "azurerm_postgresql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "14"
  sku_name            = "GP_Standard_D2s_v3"

  storage_mb = 32768

  zone = "1"
}

resource "azurerm_postgresql_flexible_server_configuration" "require_secure_transport" {
  name      = "require_secure_transport"
  server_id = azurerm_postgresql_flexible_server.example.id
  value     = "on"
}""",
        "bicep": """resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: {
    name: 'Standard_D2s_v3'
    tier: 'GeneralPurpose'
  }
  properties: {
    version: '14'
    storage: { storageSizeGB: 32 }
  }
}

resource sslConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2022-12-01' = {
  parent: pgServer
  name: 'require_secure_transport'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}""",
        "azure_cli": (
            "az postgres flexible-server parameter set"
            " --resource-group @@resource_group@@ --server-name @@name@@"
            " --name require_secure_transport --value on"
        ),
        "description": "Enforce SSL/TLS connections on the PostgreSQL flexible server.",
    },
    "CIS-AZ-40": {
        "terraform": """resource "azurerm_container_registry" "@@tf_name@@" {
  name                          = "@@name@@"
  resource_group_name           = "@@resource_group@@"
  location                      = "@@location@@"
  sku                           = "Premium"

  # Disable public network access
  public_network_access_enabled = false
}

resource "azurerm_private_endpoint" "acr" {
  name                = "pe-acr"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "acr-connection"
    private_connection_resource_id = azurerm_container_registry.example.id
    subresource_names              = ["registry"]
    is_manual_connection           = false
  }
}""",
        "bicep": """resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'Premium' }
  properties: {
    publicNetworkAccess: 'Disabled'
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = {
  name: 'pe-acr'
  location: resourceGroup().location
  properties: {
    subnet: { id: subnet.id }
    privateLinkServiceConnections: [
      {
        name: 'acr-connection'
        properties: {
          privateLinkServiceId: acr.id
          groupIds: ['registry']
        }
      }
    ]
  }
}""",
        "azure_cli": "az acr update --name @@name@@ --resource-group @@resource_group@@ --public-network-enabled false",
        "description": (
            "Disable public network access on the container registry. Requires Premium SKU and private endpoints."
        ),
    },
    "CIS-AZ-12": {
        "terraform": """resource "azurerm_storage_container" "@@tf_name@@" {
  name                  = "content"
  storage_account_name  = azurerm_storage_account.example.name
  container_access_type = "private"  # No anonymous access
}""",
        "bicep": """resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/content'
  properties: {
    publicAccess: 'None'
  }
}""",
        "azure_cli": (
            "az storage container set-permission --name @@container_name@@ --account-name @@name@@ --public-access off"
        ),
        "description": "Set blob container access level to private (no anonymous access).",
    },
    # ── Top-15 missing P0/P1 snippets (sprint 2026-04-11) ───────────────
    # Selected from IFO production data: 100% of failing P0 + top 4 P1
    # by fail count. See CHANGELOG.md entry for this sprint.
    "CIS-AZ-04": {
        "terraform": """resource "azurerm_monitor_diagnostic_setting" "@@tf_name@@" {
  name                       = "diag-activity"
  target_resource_id         = "/subscriptions/@@subscription_id@@"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id

  enabled_log {
    category = "Administrative"
  }
  enabled_log {
    category = "Security"
  }
  enabled_log {
    category = "ServiceHealth"
  }
  enabled_log {
    category = "Alert"
  }
  enabled_log {
    category = "Policy"
  }
}""",
        "bicep": """resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-activity'
  scope: subscription()
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      { category: 'Administrative', enabled: true }
      { category: 'Security', enabled: true }
      { category: 'ServiceHealth', enabled: true }
      { category: 'Alert', enabled: true }
      { category: 'Policy', enabled: true }
    ]
  }
}""",
        "azure_cli": (
            "az monitor diagnostic-settings subscription create"
            " --name diag-activity"
            " --subscription @@subscription_id@@"
            " --location westeurope"
            " --workspace @@workspace_id@@"
            ' --logs \'[{"category":"Administrative","enabled":true},'
            '{"category":"Security","enabled":true},'
            '{"category":"ServiceHealth","enabled":true},'
            '{"category":"Alert","enabled":true},'
            '{"category":"Policy","enabled":true}]\''
        ),
        "description": (
            "Stream subscription Activity Logs to a Log Analytics workspace "
            "so that administrative, security, and policy events are retained "
            "for audit and alerting."
        ),
    },
    "CIS-AZ-71": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  auth_settings_v2 {
    auth_enabled           = true
    require_authentication = true
    unauthenticated_action = "RedirectToLoginPage"
    default_provider       = "azureactivedirectory"

    active_directory_v2 {
      client_id            = var.aad_client_id
      tenant_auth_endpoint = "https://login.microsoftonline.com/${var.aad_tenant_id}/v2.0"
    }

    login {}
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: '@@name@@'
  location: location
  properties: {
    siteConfig: {
      // Auth settings are a child resource.
    }
  }
}

resource auth 'Microsoft.Web/sites/config@2022-09-01' = {
  name: 'authsettingsV2'
  parent: webApp
  properties: {
    platform: { enabled: true }
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: aadClientId
          openIdIssuer: 'https://login.microsoftonline.com/${aadTenantId}/v2.0'
        }
      }
    }
  }
}""",
        "azure_cli": (
            "az webapp auth update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --enabled true"
            " --action LoginWithAzureActiveDirectory"
            " --aad-client-id <aad-client-id>"
            " --aad-token-issuer-url https://sts.windows.net/<tenant-id>/"
        ),
        "description": (
            "Turn on built-in App Service authentication (Easy Auth) so that "
            "anonymous requests are rejected and unauthenticated users are "
            "redirected to the configured identity provider."
        ),
    },
    "CIS-AZ-74": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"

  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Reject Shared Key access — force Entra ID OAuth authentication.
  shared_access_key_enabled = false
  default_to_oauth_authentication = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
  }
}""",
        "azure_cli": (
            "az storage account update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --allow-shared-key-access false"
            " --default-to-oauth-authentication true"
        ),
        "description": (
            "Disable Shared Key (account key) access on the storage account "
            "and force clients to authenticate with Microsoft Entra ID. "
            "Prevents credential leakage via connection strings."
        ),
    },
    "CIS-AZ-92": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    minimum_tls_version       = "1.2"
    # Enforce a strong cipher suite baseline (Azure uses FrontEnd).
    min_tls_cipher_suite      = "TLS_AES_128_GCM_SHA256"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: '@@name@@'
  location: location
  properties: {
    siteConfig: {
      minTlsVersion: '1.2'
      minTlsCipherSuite: 'TLS_AES_128_GCM_SHA256'
    }
  }
}""",
        "azure_cli": (
            "az webapp config set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --min-tls-version 1.2"
            " --min-tls-cipher-suite TLS_AES_128_GCM_SHA256"
        ),
        "description": (
            "Set the minimum TLS cipher suite to a modern AEAD (GCM) baseline "
            "so that weak CBC ciphers and legacy RSA key exchange are rejected."
        ),
    },
    "CIS-AZ-94": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    ip_restriction_default_action = "Deny"

    ip_restriction {
      name        = "allow-corporate-network"
      priority    = 100
      action      = "Allow"
      ip_address  = "203.0.113.0/24"   # Replace with your public CIDR
    }

    ip_restriction {
      name        = "allow-vnet"
      priority    = 200
      action      = "Allow"
      service_tag = "VirtualNetwork"
    }
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: '@@name@@'
  location: location
  properties: {
    siteConfig: {
      ipSecurityRestrictionsDefaultAction: 'Deny'
      ipSecurityRestrictions: [
        {
          name: 'allow-corporate-network'
          priority: 100
          action: 'Allow'
          ipAddress: '203.0.113.0/24'
        }
        {
          name: 'allow-vnet'
          priority: 200
          action: 'Allow'
          tag: 'ServiceTag'
          ipAddress: 'VirtualNetwork'
        }
      ]
    }
  }
}""",
        "azure_cli": (
            "az webapp config access-restriction add"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --rule-name allow-corporate-network"
            " --priority 100"
            " --action Allow"
            " --ip-address 203.0.113.0/24\n"
            "az webapp config access-restriction set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --use-same-restrictions-for-scm-site true"
        ),
        "description": (
            "Attach IP access restrictions to the web app so that only "
            "approved CIDR blocks or service tags can reach the public "
            "endpoint. Default action is Deny."
        ),
    },
    "CIS-AZ-104": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "vm" {
  tier          = "Standard"
  resource_type = "VirtualMachines"
}""",
        "bicep": """resource defenderVM 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'VirtualMachines'
  properties: {
    pricingTier: 'Standard'
  }
}""",
        "azure_cli": (
            "az security pricing create --name VirtualMachines --tier Standard --subscription @@subscription_id@@"
        ),
        "description": (
            "Enable Microsoft Defender for Servers (Plan 2 by default) on "
            "the subscription to get agent-based vulnerability assessment, "
            "file integrity monitoring, and adaptive application controls."
        ),
    },
    "CIS-AZ-105": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "storage" {
  tier          = "Standard"
  resource_type = "StorageAccounts"
  subplan       = "DefenderForStorageV2"
}""",
        "bicep": """resource defenderStorage 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'StorageAccounts'
  properties: {
    pricingTier: 'Standard'
    subPlan: 'DefenderForStorageV2'
  }
}""",
        "azure_cli": (
            "az security pricing create"
            " --name StorageAccounts"
            " --tier Standard"
            " --subplan DefenderForStorageV2"
            " --subscription @@subscription_id@@"
        ),
        "description": (
            "Enable Microsoft Defender for Storage (v2) on the subscription "
            "to get malware scanning on upload, sensitive data discovery, "
            "and activity monitoring."
        ),
    },
    "CIS-AZ-106": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "sql" {
  tier          = "Standard"
  resource_type = "SqlServers"
}

resource "azurerm_security_center_subscription_pricing" "sqlvm" {
  tier          = "Standard"
  resource_type = "SqlServerVirtualMachines"
}""",
        "bicep": """resource defenderSql 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'SqlServers'
  properties: { pricingTier: 'Standard' }
}

resource defenderSqlVm 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'SqlServerVirtualMachines'
  properties: { pricingTier: 'Standard' }
}""",
        "azure_cli": (
            "az security pricing create --name SqlServers --tier Standard"
            " --subscription @@subscription_id@@\n"
            "az security pricing create --name SqlServerVirtualMachines --tier Standard"
            " --subscription @@subscription_id@@"
        ),
        "description": (
            "Enable Microsoft Defender for SQL on both Azure SQL databases "
            "and SQL on VM. Provides advanced threat protection, "
            "vulnerability assessment, and data classification."
        ),
    },
    "CIS-AZ-107": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "appservice" {
  tier          = "Standard"
  resource_type = "AppServices"
}""",
        "bicep": """resource defenderAppService 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'AppServices'
  properties: { pricingTier: 'Standard' }
}""",
        "azure_cli": (
            "az security pricing create --name AppServices --tier Standard --subscription @@subscription_id@@"
        ),
        "description": (
            "Enable Microsoft Defender for App Service on the subscription "
            "to detect runtime threats, anomalous traffic patterns, and "
            "known-vulnerable dependencies on every web app in the scope."
        ),
    },
    "CIS-AZ-108": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "containers" {
  tier          = "Standard"
  resource_type = "Containers"
}""",
        "bicep": """resource defenderContainers 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'Containers'
  properties: { pricingTier: 'Standard' }
}""",
        "azure_cli": (
            "az security pricing create --name Containers --tier Standard --subscription @@subscription_id@@"
        ),
        "description": (
            "Enable Microsoft Defender for Containers on the subscription. "
            "Provides image scanning in ACR, Kubernetes audit log analysis, "
            "and runtime threat detection on AKS clusters."
        ),
    },
    "CIS-AZ-109": {
        "terraform": """resource "azurerm_security_center_subscription_pricing" "keyvault" {
  tier          = "Standard"
  resource_type = "KeyVaults"
}""",
        "bicep": """resource defenderKeyVault 'Microsoft.Security/pricings@2024-01-01' = {
  name: 'KeyVaults'
  properties: { pricingTier: 'Standard' }
}""",
        "azure_cli": ("az security pricing create --name KeyVaults --tier Standard --subscription @@subscription_id@@"),
        "description": (
            "Enable Microsoft Defender for Key Vault on the subscription "
            "to detect suspicious access patterns, credential harvesting "
            "attempts, and unusual secret retrieval."
        ),
    },
    "CIS-AZ-26": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  identity {
    type = "SystemAssigned"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: '@@name@@'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
  }
}""",
        "azure_cli": ("az webapp identity assign --name @@name@@ --resource-group @@resource_group@@"),
        "description": (
            "Enable a system-assigned managed identity on the web app so "
            "it can authenticate to Key Vault, Storage, SQL, and other "
            "Azure resources without storing secrets in app settings."
        ),
    },
    "CIS-AZ-90": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    health_check_path                 = "/healthz"
    health_check_eviction_time_in_min = 5
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: '@@name@@'
  location: location
  properties: {
    siteConfig: {
      healthCheckPath: '/healthz'
    }
  }
}""",
        "azure_cli": (
            "az webapp config set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            ' --generic-configurations \'{"healthCheckPath":"/healthz"}\''
        ),
        "description": (
            "Configure a health check path so App Service can automatically "
            "remove unhealthy instances from the load-balancer rotation and "
            "stream health events to diagnostic logs."
        ),
    },
    "CIS-AZ-91": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    auto_heal_enabled = true
    auto_heal_setting {
      trigger {
        requests {
          count    = 500
          interval = "00:05:00"
        }
      }
      action {
        action_type = "Recycle"
      }
    }
  }
}""",
        "bicep": """resource webAppConfig 'Microsoft.Web/sites/config@2022-09-01' = {
  name: 'web'
  parent: webApp
  properties: {
    autoHealEnabled: true
    autoHealRules: {
      triggers: {
        requests: {
          count: 500
          timeInterval: '00:05:00'
        }
      }
      actions: {
        actionType: 'Recycle'
      }
    }
  }
}""",
        "azure_cli": (
            "az webapp config set --name @@name@@ --resource-group @@resource_group@@ --auto-heal-enabled true"
        ),
        "description": (
            "Enable auto-heal rules on the web app so the platform recycles "
            "instances that exhibit error patterns (slow requests, memory "
            "spikes, excessive request rate) without manual intervention."
        ),
    },
    "CIS-AZ-156": {
        "terraform": """resource "azurerm_monitor_diagnostic_setting" "webapp" {
  name                       = "diag-@@name@@"
  target_resource_id         = azurerm_linux_web_app.example.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id

  enabled_log {
    category = "AppServiceHTTPLogs"
  }
  enabled_log {
    category = "AppServiceConsoleLogs"
  }
  enabled_log {
    category = "AppServiceAppLogs"
  }
  enabled_log {
    category = "AppServiceAuditLogs"
  }
  enabled_log {
    category = "AppServiceIPSecAuditLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}""",
        "bicep": """resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diag-@@name@@'
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      { category: 'AppServiceHTTPLogs', enabled: true }
      { category: 'AppServiceConsoleLogs', enabled: true }
      { category: 'AppServiceAppLogs', enabled: true }
      { category: 'AppServiceAuditLogs', enabled: true }
      { category: 'AppServiceIPSecAuditLogs', enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}""",
        "azure_cli": (
            "az monitor diagnostic-settings create"
            " --name diag-@@name@@"
            " --resource /subscriptions/@@subscription_id@@/resourceGroups"
            "/@@resource_group@@/providers/Microsoft.Web/sites/@@name@@"
            " --workspace @@workspace_id@@"
            ' --logs \'[{"category":"AppServiceHTTPLogs","enabled":true},'
            '{"category":"AppServiceConsoleLogs","enabled":true},'
            '{"category":"AppServiceAppLogs","enabled":true},'
            '{"category":"AppServiceAuditLogs","enabled":true},'
            '{"category":"AppServiceIPSecAuditLogs","enabled":true}]\''
            ' --metrics \'[{"category":"AllMetrics","enabled":true}]\''
        ),
        "description": (
            "Attach a diagnostic setting to the web app so that HTTP logs, "
            "app logs, console logs, audit logs, and IPSec audit logs stream "
            "to a Log Analytics workspace for long-term retention and query."
        ),
    },
}


def get_remediation_for_control(control_code: str) -> dict[str, str] | None:
    """Return remediation snippets for a given control code, or None if not available."""
    return REMEDIATION_SNIPPETS.get(control_code)


def _apply_markers(template: str, vars_: dict[str, str]) -> str:
    """Replace `@@key@@` markers in `template` with values from `vars_`.

    Unknown markers are left intact — the renderer never raises for a
    placeholder that doesn't map to an asset var, which lets snippet
    authors use exotic markers (e.g. `@@pg_server@@`) that won't be
    available on every asset.
    """
    out = template
    for key, value in vars_.items():
        out = out.replace(f"@@{key}@@", value)
    return out


def _sanitize_tf_name(name: str) -> str:
    """Convert an Azure resource name to a valid Terraform/Bicep identifier.

    Terraform resource labels must match `[A-Za-z_][A-Za-z0-9_-]*` and by
    convention use lowercase snake_case. Azure resource names commonly
    contain hyphens (`ifo-eva-pdta-webapp-test`) which are valid in TF
    labels but look odd mixed with snake_case references. We convert
    hyphens and dots to underscores and lowercase the result so the
    label reads like a natural local identifier.
    """
    if not name:
        return "target"
    sanitized = name.lower().replace("-", "_").replace(".", "_")
    if sanitized[0].isdigit():
        sanitized = f"r_{sanitized}"
    return sanitized


def render_for_asset(control_code: str, asset: Asset | None) -> tuple[dict[str, str] | None, bool]:
    """Render the snippet bundle for `control_code` using `asset` values.

    Returns a tuple of:
        - the snippet dict with `@@placeholder@@` markers substituted,
          or `None` if there is no snippet for this control code;
        - a boolean `filled` flag: True when substitution successfully
          ran against a parsed ARM ID (regardless of whether the snippet
          actually contained any markers — a snippet may be generic but
          we still want to show the "for this asset" badge). False only
          when there is no asset, no provider_id, or the ARM ID can't
          be parsed.

    The caller uses `filled` to decide whether to show the
    "Filled for <asset.name>" badge in the UI.

    Template vars beyond those from `ArmId.as_template_vars()`:
        @@tf_name@@    sanitized asset name usable as a Terraform /
                       Bicep local identifier (hyphens -> underscores)
        @@location@@   Azure region from `asset.region`, e.g. "westeurope"
    """
    from app.utils.arm_id import parse_provider_id  # local import avoids cycle

    raw = REMEDIATION_SNIPPETS.get(control_code)
    if raw is None:
        return None, False

    arm = parse_provider_id(asset.provider_id) if asset is not None else None
    if arm is None or not arm.subscription_id:
        return dict(raw), False

    vars_ = arm.as_template_vars()
    # Extra vars sourced from the Asset object itself, not the ARM ID.
    if asset is not None:
        vars_["tf_name"] = _sanitize_tf_name(arm.name or asset.name or "")
        vars_["location"] = asset.region or ""

    rendered: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            rendered[key] = _apply_markers(value, vars_)
        else:
            rendered[key] = value  # type: ignore[assignment]

    # "Filled" means substitution happened on a real ARM ID that has at
    # least the subscription + one of (resource_group, name).
    filled = bool(arm.subscription_id and (arm.resource_group or arm.name))
    return rendered, filled
