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
    # ── SQL DB TDE ─────────────────────────────────────────────────────
    "CIS-AZ-08": {
        "terraform": """resource "azurerm_mssql_database" "@@tf_name@@" {
  name      = "@@name@@"
  server_id = azurerm_mssql_server.example.id

  transparent_data_encryption_enabled = true
}""",
        "bicep": """resource sqlDb 'Microsoft.Sql/servers/databases@2023-02-01-preview' = {
  name: '@@name@@'
  parent: sqlServer
  location: resourceGroup().location
  properties: {}
}

resource tde 'Microsoft.Sql/servers/databases/transparentDataEncryption@2023-02-01-preview' = {
  name: 'current'
  parent: sqlDb
  properties: {
    state: 'Enabled'
  }
}""",
        "azure_cli": (
            "az sql db tde set --database @@name@@"
            " --server @@server_name@@"
            " --resource-group @@resource_group@@"
            " --status Enabled"
        ),
        "description": (
            "Enable Transparent Data Encryption (TDE) on the SQL database "
            "to encrypt data at rest with a service-managed or "
            "customer-managed key."
        ),
    },
    # ── Web App – remote debugging ─────────────────────────────────────
    "CIS-AZ-24": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    remote_debugging_enabled = false
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      remoteDebuggingEnabled: false
    }
  }
}""",
        "azure_cli": (
            "az webapp config set --name @@name@@ --resource-group @@resource_group@@ --remote-debugging-enabled false"
        ),
        "description": (
            "Disable remote debugging on the web app. Remote debugging "
            "opens additional ports and should be turned off in production."
        ),
    },
    # ── SQL Server – Azure AD admin ────────────────────────────────────
    "CIS-AZ-29": {
        "terraform": """resource "azurerm_mssql_server_active_directory_administrator" "@@tf_name@@" {
  server_id           = azurerm_mssql_server.example.id
  login               = "AzureAD Admin"
  object_id           = var.aad_admin_object_id
  tenant_id           = data.azurerm_client_config.current.tenant_id
  azuread_authentication_only = true
}""",
        "bicep": """resource sqlAdAdmin 'Microsoft.Sql/servers/administrators@2023-02-01-preview' = {
  name: 'ActiveDirectory'
  parent: sqlServer
  properties: {
    administratorType: 'ActiveDirectory'
    login: 'AzureAD Admin'
    sid: aadAdminObjectId
    tenantId: subscription().tenantId
    azureADOnlyAuthentication: true
  }
}""",
        "azure_cli": (
            "az sql server ad-admin create"
            " --server-name @@name@@"
            " --resource-group @@resource_group@@"
            " --display-name 'AzureAD Admin'"
            " --object-id <aad-admin-object-id>"
        ),
        "description": (
            "Provision an Azure AD administrator for the SQL Server "
            "so that authentication uses centralized identity instead of "
            "SQL authentication."
        ),
    },
    # ── SQL Server – auditing ──────────────────────────────────────────
    "CIS-AZ-30": {
        "terraform": """resource "azurerm_mssql_server_extended_auditing_policy" "@@tf_name@@" {
  server_id                  = azurerm_mssql_server.example.id
  log_monitoring_enabled     = true
  storage_endpoint           = azurerm_storage_account.audit.primary_blob_endpoint
  storage_account_access_key = azurerm_storage_account.audit.primary_access_key
  retention_in_days          = 90
}""",
        "bicep": """resource sqlAudit 'Microsoft.Sql/servers/auditingSettings@2023-02-01-preview' = {
  name: 'default'
  parent: sqlServer
  properties: {
    state: 'Enabled'
    isAzureMonitorTargetEnabled: true
    retentionDays: 90
  }
}""",
        "azure_cli": (
            "az sql server audit-policy update"
            " --server @@name@@"
            " --resource-group @@resource_group@@"
            " --state Enabled"
            " --lats Enabled"
            " --lawri @@workspace_id@@"
        ),
        "description": (
            "Enable auditing on the SQL Server to capture database events "
            "and send them to Log Analytics or a storage account for "
            "compliance and forensics."
        ),
    },
    # ── VM – managed disks ─────────────────────────────────────────────
    "CIS-AZ-31": {
        "terraform": """resource "azurerm_virtual_machine" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  vm_size             = "Standard_D2s_v3"

  storage_os_disk {
    name              = "@@name@@-osdisk"
    managed_disk_type = "Premium_LRS"
    create_option     = "FromImage"
  }
}""",
        "bicep": """resource vm 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    storageProfile: {
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
      }
    }
  }
}""",
        "azure_cli": ("az vm convert --resource-group @@resource_group@@ --name @@name@@"),
        "description": (
            "Convert VM to use managed disks. Managed disks provide "
            "better reliability, security isolation, and built-in "
            "encryption support."
        ),
    },
    # ── VM – disk encryption ──────────────────────────────────────────
    "CIS-AZ-32": {
        "terraform": """resource "azurerm_virtual_machine_extension" "disk_encryption" {
  name                 = "AzureDiskEncryption"
  virtual_machine_id   = azurerm_linux_virtual_machine.example.id
  publisher            = "Microsoft.Azure.Security"
  type                 = "AzureDiskEncryptionForLinux"
  type_handler_version = "1.1"

  settings = jsonencode({
    EncryptionOperation = "EnableEncryption"
    KeyVaultURL         = azurerm_key_vault.example.vault_uri
    KeyVaultResourceId  = azurerm_key_vault.example.id
    VolumeType          = "All"
  })
}""",
        "bicep": """resource diskEncryption 'Microsoft.Compute/virtualMachines/extensions@2023-07-01' = {
  name: 'AzureDiskEncryption'
  parent: vm
  location: resourceGroup().location
  properties: {
    publisher: 'Microsoft.Azure.Security'
    type: 'AzureDiskEncryptionForLinux'
    typeHandlerVersion: '1.1'
    settings: {
      EncryptionOperation: 'EnableEncryption'
      KeyVaultURL: keyVault.properties.vaultUri
      KeyVaultResourceId: keyVault.id
      VolumeType: 'All'
    }
  }
}""",
        "azure_cli": (
            "az vm encryption enable"
            " --resource-group @@resource_group@@"
            " --name @@name@@"
            " --disk-encryption-keyvault @@keyvault_name@@"
            " --volume-type All"
        ),
        "description": (
            "Enable Azure Disk Encryption on the VM to encrypt OS and "
            "data disks using BitLocker (Windows) or dm-crypt (Linux) "
            "with keys protected by Key Vault."
        ),
    },
    # ── VM – boot diagnostics ────────────────────────────────────────
    "CIS-AZ-33": {
        "terraform": """resource "azurerm_linux_virtual_machine" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  size                = "Standard_D2s_v3"
  admin_username      = "azureuser"

  boot_diagnostics {
    # Use managed storage (empty block = Azure-managed)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }
}""",
        "bicep": """resource vm 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}""",
        "azure_cli": ("az vm boot-diagnostics enable --resource-group @@resource_group@@ --name @@name@@"),
        "description": (
            "Enable boot diagnostics on the VM to capture serial console "
            "output and screenshots for troubleshooting boot failures."
        ),
    },
    # ── VM – secure boot ─────────────────────────────────────────────
    "CIS-AZ-34": {
        "terraform": """resource "azurerm_linux_virtual_machine" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  size                = "Standard_D2s_v3"
  admin_username      = "azureuser"

  secure_boot_enabled = true
  vtpm_enabled        = true

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    security_encryption_type = "VMGuestStateOnly"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}""",
        "bicep": """resource vm 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    securityProfile: {
      securityType: 'TrustedLaunch'
      uefiSettings: {
        secureBootEnabled: true
        vTpmEnabled: true
      }
    }
  }
}""",
        "azure_cli": (
            "# Secure boot must be set at VM creation time (Gen2 VM).\n"
            "az vm create --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --image Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest"
            " --security-type TrustedLaunch"
            " --enable-secure-boot true --enable-vtpm true"
        ),
        "description": (
            "Enable Secure Boot and vTPM via Trusted Launch on the VM "
            "to protect against bootkits and rootkits. Requires a Gen2 "
            "VM image."
        ),
    },
    # ── Cosmos DB – VNet filter ───────────────────────────────────────
    "CIS-AZ-36": {
        "terraform": """resource "azurerm_cosmosdb_account" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  is_virtual_network_filter_enabled = true

  virtual_network_rule {
    id = azurerm_subnet.example.id
  }

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
    isVirtualNetworkFilterEnabled: true
    virtualNetworkRules: [
      { id: subnet.id }
    ]
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
            "az cosmosdb update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --enable-virtual-network true"
            " --virtual-network-rules @@subnet_id@@"
        ),
        "description": (
            "Enable virtual network filtering on the Cosmos DB account to restrict access to specific subnets."
        ),
    },
    # ── PostgreSQL – log checkpoints ──────────────────────────────────
    "CIS-AZ-38": {
        "terraform": """resource "azurerm_postgresql_flexible_server_configuration" "log_checkpoints" {
  name      = "log_checkpoints"
  server_id = azurerm_postgresql_flexible_server.example.id
  value     = "on"
}""",
        "bicep": """resource logCheckpoints 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2022-12-01' = {
  parent: pgServer
  name: 'log_checkpoints'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}""",
        "azure_cli": (
            "az postgres flexible-server parameter set"
            " --resource-group @@resource_group@@"
            " --server-name @@name@@"
            " --name log_checkpoints --value on"
        ),
        "description": (
            "Enable log_checkpoints on the PostgreSQL server to record "
            "checkpoint activity for performance monitoring and audit."
        ),
    },
    # ── App Gateway – WAF enabled ────────────────────────────────────
    "CIS-AZ-43": {
        "terraform": """resource "azurerm_web_application_firewall_policy" "@@tf_name@@" {
  name                = "waf-policy-@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"

  policy_settings {
    enabled = true
    mode    = "Prevention"
  }

  managed_rules {
    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }
  }
}""",
        "bicep": """resource wafPolicy \
  'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2023-04-01' = {
  name: 'waf-policy-@@name@@'
  location: resourceGroup().location
  properties: {
    policySettings: {
      state: 'Enabled'
      mode: 'Prevention'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      ]
    }
  }
}""",
        "azure_cli": (
            "az network application-gateway waf-policy create"
            " --name waf-policy-@@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --type OWASP --version 3.2"
        ),
        "description": (
            "Create a WAF policy with OWASP 3.2 managed rules in "
            "Prevention mode and attach it to the Application Gateway."
        ),
    },
    # ── App Gateway – WAF v2 SKU ─────────────────────────────────────
    "CIS-AZ-44": {
        "terraform": """resource "azurerm_application_gateway" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"

  sku {
    name     = "WAF_v2"
    tier     = "WAF_v2"
    capacity = 2
  }

  gateway_ip_configuration {
    name      = "gateway-ip"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_port {
    name = "https"
    port = 443
  }

  frontend_ip_configuration {
    name                 = "public"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }
}""",
        "bicep": """resource appGateway 'Microsoft.Network/applicationGateways@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    sku: {
      name: 'WAF_v2'
      tier: 'WAF_v2'
      capacity: 2
    }
  }
}""",
        "azure_cli": (
            "# WAF_v2 SKU must be set at creation time.\n"
            "# Existing gateways require recreation.\n"
            "az network application-gateway create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --sku WAF_v2 --capacity 2"
            " --subnet @@subnet_id@@"
        ),
        "description": (
            "Use the WAF_v2 SKU tier on the Application Gateway for "
            "autoscaling, zone redundancy, and improved WAF performance."
        ),
    },
    # ── Public IP – DDoS protection ──────────────────────────────────
    "CIS-AZ-45": {
        "terraform": """resource "azurerm_public_ip" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  allocation_method   = "Static"
  sku                 = "Standard"

  ddos_protection_mode = "Enabled"
  ddos_protection_plan_id = azurerm_network_ddos_protection_plan.example.id
}""",
        "bicep": """resource publicIp 'Microsoft.Network/publicIPAddresses@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'Standard' }
  properties: {
    publicIPAllocationMethod: 'Static'
    ddosSettings: {
      protectionMode: 'Enabled'
      ddosProtectionPlan: {
        id: ddosPlan.id
      }
    }
  }
}""",
        "azure_cli": (
            "az network public-ip update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --ddos-protection-mode Enabled"
            " --ddos-protection-plan @@ddos_plan_id@@"
        ),
        "description": (
            "Enable DDoS Protection Standard on the public IP address "
            "to get automatic traffic profiling and attack mitigation."
        ),
    },
    # ── VNet – DDoS protection plan ──────────────────────────────────
    "CIS-AZ-46": {
        "terraform": """resource "azurerm_network_ddos_protection_plan" "example" {
  name                = "ddos-plan"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
}

resource "azurerm_virtual_network" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  address_space       = ["10.0.0.0/16"]

  ddos_protection_plan {
    id     = azurerm_network_ddos_protection_plan.example.id
    enable = true
  }
}""",
        "bicep": """resource ddosPlan 'Microsoft.Network/ddosProtectionPlans@2023-04-01' = {
  name: 'ddos-plan'
  location: resourceGroup().location
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    addressSpace: { addressPrefixes: ['10.0.0.0/16'] }
    enableDdosProtection: true
    ddosProtectionPlan: { id: ddosPlan.id }
  }
}""",
        "azure_cli": (
            "az network ddos-protection create"
            " --name ddos-plan"
            " --resource-group @@resource_group@@"
            " --location @@location@@\n"
            "az network vnet update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --ddos-protection-plan ddos-plan"
            " --ddos-protection true"
        ),
        "description": (
            "Attach a DDoS Protection Standard plan to the virtual "
            "network to protect all public endpoints within the VNet."
        ),
    },
    # ── Network Watcher ──────────────────────────────────────────────
    "CIS-AZ-47": {
        "terraform": """resource "azurerm_network_watcher" "@@tf_name@@" {
  name                = "NetworkWatcher_@@location@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
}""",
        "bicep": """resource networkWatcher 'Microsoft.Network/networkWatchers@2023-04-01' = {
  name: 'NetworkWatcher_@@location@@'
  location: '@@location@@'
}""",
        "azure_cli": (
            "az network watcher configure --resource-group @@resource_group@@ --locations @@location@@ --enabled true"
        ),
        "description": (
            "Enable Network Watcher in each Azure region used to provide "
            "network diagnostics, NSG flow logs, and packet capture."
        ),
    },
    # ── VPN Gateway – non-basic SKU ──────────────────────────────────
    "CIS-AZ-48": {
        "terraform": """resource "azurerm_virtual_network_gateway" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  type                = "Vpn"
  vpn_type            = "RouteBased"
  sku                 = "VpnGw1"

  ip_configuration {
    name                 = "vnetGatewayConfig"
    public_ip_address_id = azurerm_public_ip.vpn.id
    subnet_id            = azurerm_subnet.gateway.id
  }
}""",
        "bicep": """resource vpnGateway 'Microsoft.Network/virtualNetworkGateways@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    gatewayType: 'Vpn'
    vpnType: 'RouteBased'
    sku: {
      name: 'VpnGw1'
      tier: 'VpnGw1'
    }
    ipConfigurations: [
      {
        name: 'vnetGatewayConfig'
        properties: {
          publicIPAddress: { id: publicIp.id }
          subnet: { id: gatewaySubnet.id }
        }
      }
    ]
  }
}""",
        "azure_cli": (
            "# VPN Gateway SKU cannot be changed in place from Basic.\n"
            "# Recreate the gateway with VpnGw1 or higher:\n"
            "az network vnet-gateway create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --sku VpnGw1 --gateway-type Vpn --vpn-type RouteBased"
            " --public-ip-address @@pip_name@@"
            " --vnet @@vnet_name@@"
        ),
        "description": (
            "Upgrade the VPN Gateway from Basic to VpnGw1 or higher. "
            "Basic SKU lacks IKEv2, active-active, and zone redundancy."
        ),
    },
    # ── Front Door – WAF policy ──────────────────────────────────────
    "CIS-AZ-49": {
        "terraform": """resource "azurerm_cdn_frontdoor_firewall_policy" "@@tf_name@@" {
  name                = "wafpolicy@@tf_name@@"
  resource_group_name = "@@resource_group@@"
  sku_name            = "Premium_AzureFrontDoor"
  mode                = "Prevention"
  enabled             = true

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.0"
    action  = "Block"
  }
}""",
        "bicep": """resource wafPolicy 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2022-05-01' = {
  name: 'wafpolicy@@name@@'
  location: 'Global'
  sku: { name: 'Premium_AzureFrontDoor' }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
        }
        {
          ruleSetType: 'Microsoft_BotManagerRuleSet'
          ruleSetVersion: '1.0'
        }
      ]
    }
  }
}""",
        "azure_cli": (
            "az network front-door waf-policy create"
            " --name wafpolicy@@name@@"
            " --resource-group @@resource_group@@"
            " --sku Premium_AzureFrontDoor"
            " --mode Prevention"
        ),
        "description": (
            "Create a WAF policy for Front Door with managed rule sets "
            "in Prevention mode and attach it to frontend endpoints."
        ),
    },
    # ── Front Door – HTTPS redirect ──────────────────────────────────
    "CIS-AZ-50": {
        "terraform": """resource "azurerm_cdn_frontdoor_rule" "https_redirect" {
  name                      = "httpsRedirect"
  cdn_frontdoor_rule_set_id = azurerm_cdn_frontdoor_rule_set.example.id
  order                     = 0

  conditions {
    request_scheme_condition {
      match_values = ["HTTP"]
      operator     = "Equal"
    }
  }

  actions {
    url_redirect_action {
      redirect_type     = "PermanentRedirect"
      redirect_protocol = "Https"
    }
  }
}""",
        "bicep": """resource redirectRule 'Microsoft.Cdn/profiles/ruleSets/rules@2023-05-01' = {
  name: 'httpsRedirect'
  parent: ruleSet
  properties: {
    order: 0
    conditions: [
      {
        name: 'RequestScheme'
        parameters: {
          typeName: 'DeliveryRuleRequestSchemeConditionParameters'
          matchValues: ['HTTP']
          operator: 'Equal'
        }
      }
    ]
    actions: [
      {
        name: 'UrlRedirect'
        parameters: {
          typeName: 'DeliveryRuleUrlRedirectActionParameters'
          redirectType: 'PermanentRedirect'
          destinationProtocol: 'Https'
        }
      }
    ]
  }
}""",
        "azure_cli": (
            "az afd rule create"
            " --rule-name httpsRedirect"
            " --profile-name @@name@@"
            " --resource-group @@resource_group@@"
            " --rule-set-name DefaultRuleSet"
            " --order 0"
            " --match-variable RequestScheme"
            " --operator Equal --match-values HTTP"
            " --action-name UrlRedirect"
            " --redirect-protocol Https"
            " --redirect-type PermanentRedirect"
        ),
        "description": (
            "Add an HTTP-to-HTTPS redirect rule on Front Door so that "
            "all plain HTTP requests are permanently redirected to HTTPS."
        ),
    },
    # ── Web App – client cert auth ───────────────────────────────────
    "CIS-AZ-67": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  client_certificate_enabled = true
  client_certificate_mode    = "Required"

  site_config {}
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    clientCertEnabled: true
    clientCertMode: 'Required'
  }
}""",
        "azure_cli": (
            "az webapp update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --set clientCertEnabled=true"
            " clientCertMode=Required"
        ),
        "description": (
            "Require client certificate authentication on the web app. "
            "Clients must present a valid TLS certificate to access "
            "the application."
        ),
    },
    # ── Web App – Always On ──────────────────────────────────────────
    "CIS-AZ-68": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    always_on = true
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      alwaysOn: true
    }
  }
}""",
        "azure_cli": ("az webapp config set --name @@name@@ --resource-group @@resource_group@@ --always-on true"),
        "description": (
            "Enable Always On on the web app to prevent it from being "
            "unloaded during idle periods, avoiding cold-start latency."
        ),
    },
    # ── Web App – HTTP/2 ─────────────────────────────────────────────
    "CIS-AZ-69": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    http2_enabled = true
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      http20Enabled: true
    }
  }
}""",
        "azure_cli": ("az webapp config set --name @@name@@ --resource-group @@resource_group@@ --http20-enabled true"),
        "description": (
            "Enable HTTP/2 on the web app for multiplexed connections, header compression, and improved latency."
        ),
    },
    # ── App Service Plan – not Free/Shared ───────────────────────────
    "CIS-AZ-85": {
        "terraform": """resource "azurerm_service_plan" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  os_type             = "Linux"
  sku_name            = "B1"  # Basic tier minimum for production
}""",
        "bicep": """resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
}""",
        "azure_cli": ("az appservice plan update --name @@name@@ --resource-group @@resource_group@@ --sku B1"),
        "description": (
            "Upgrade the App Service Plan from Free/Shared to Basic or "
            "higher. Free and Shared tiers lack SLA, custom domains, "
            "and always-on support."
        ),
    },
    # ── App Service Plan – zone redundancy ───────────────────────────
    "CIS-AZ-86": {
        "terraform": """resource "azurerm_service_plan" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  os_type             = "Linux"
  sku_name            = "P1v3"

  zone_balancing_enabled = true
  worker_count           = 3
}""",
        "bicep": """resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'linux'
  sku: {
    name: 'P1v3'
    tier: 'PremiumV3'
  }
  properties: {
    reserved: true
    zoneRedundant: true
    numberOfWorkers: 3
  }
}""",
        "azure_cli": (
            "# Zone redundancy must be set at plan creation time:\n"
            "az appservice plan create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --sku P1v3"
            " --zone-redundant true"
            " --number-of-workers 3"
        ),
        "description": (
            "Enable zone redundancy on the App Service Plan. Requires "
            "Premium v2/v3 SKU and at least 3 workers to spread across "
            "availability zones."
        ),
    },
    # ── App Service Plan – multiple workers ──────────────────────────
    "CIS-AZ-87": {
        "terraform": """resource "azurerm_service_plan" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  os_type             = "Linux"
  sku_name            = "B1"

  worker_count = 2
}""",
        "bicep": """resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'linux'
  sku: { name: 'B1' }
  properties: {
    reserved: true
    numberOfWorkers: 2
  }
}""",
        "azure_cli": (
            "az appservice plan update --name @@name@@ --resource-group @@resource_group@@ --number-of-workers 2"
        ),
        "description": (
            "Scale the App Service Plan to at least 2 workers for high "
            "availability so the app remains available if one instance "
            "fails or restarts."
        ),
    },
    # ── App Service Plan – per-site scaling ──────────────────────────
    "CIS-AZ-88": {
        "terraform": """resource "azurerm_service_plan" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  os_type             = "Linux"
  sku_name            = "S1"

  per_site_scaling_enabled = true
}""",
        "bicep": """resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'linux'
  sku: { name: 'S1' }
  properties: {
    reserved: true
    perSiteScaling: true
  }
}""",
        "azure_cli": (
            "az appservice plan update --name @@name@@ --resource-group @@resource_group@@ --per-site-scaling true"
        ),
        "description": (
            "Enable per-site scaling on the App Service Plan so that "
            "each site can scale independently when multiple apps share "
            "the same plan."
        ),
    },
    # ── Web App – CORS no wildcard ───────────────────────────────────
    "CIS-AZ-89": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    cors {
      allowed_origins = [
        "https://app.example.com",
        "https://admin.example.com",
      ]
    }
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      cors: {
        allowedOrigins: [
          'https://app.example.com'
          'https://admin.example.com'
        ]
      }
    }
  }
}""",
        "azure_cli": (
            "az webapp cors remove --name @@name@@"
            " --resource-group @@resource_group@@"
            " --allowed-origins '*'\n"
            "az webapp cors add --name @@name@@"
            " --resource-group @@resource_group@@"
            " --allowed-origins https://app.example.com"
        ),
        "description": (
            "Remove the wildcard '*' from CORS allowed origins and "
            "replace it with explicit origin URLs to prevent cross-site "
            "request abuse."
        ),
    },
    # ── Web App – public access off (private endpoint) ───────────────
    "CIS-AZ-93": {
        "terraform": """resource "azurerm_linux_web_app" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  service_plan_id     = azurerm_service_plan.example.id

  public_network_access_enabled = false

  site_config {}
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    publicNetworkAccess: 'Disabled'
  }
}""",
        "azure_cli": (
            "az webapp update --name @@name@@ --resource-group @@resource_group@@ --set publicNetworkAccess=Disabled"
        ),
        "description": (
            "Disable public network access on the web app when a "
            "private endpoint is configured, preventing dual-path "
            "exposure."
        ),
    },
    # ── Storage – cross-tenant replication ────────────────────────────
    "CIS-AZ-95": {
        "terraform": """resource "azurerm_storage_account" "@@tf_name@@" {
  name                      = "@@name@@"
  resource_group_name       = "@@resource_group@@"
  location                  = "@@location@@"
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  cross_tenant_replication_enabled = false
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowCrossTenantReplication: false
  }
}""",
        "azure_cli": (
            "az storage account update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --allow-cross-tenant-replication false"
        ),
        "description": (
            "Disable cross-tenant replication on the storage account "
            "to prevent data exfiltration to another Azure AD tenant."
        ),
    },
    # ── Subscription – security contact email ────────────────────────
    "CIS-AZ-110": {
        "terraform": """resource "azurerm_security_center_contact" "@@tf_name@@" {
  email               = "security@example.com"
  phone               = "+1-555-0100"
  alert_notifications = true
  alerts_to_admins    = true
}""",
        "bicep": """resource secContact 'Microsoft.Security/securityContacts@2020-01-01-preview' = {
  name: 'default'
  properties: {
    emails: 'security@example.com'
    phone: '+1-555-0100'
    alertNotifications: {
      state: 'On'
      minimalSeverity: 'Medium'
    }
    notificationsByRole: {
      state: 'On'
      roles: ['Owner', 'ServiceAdmin']
    }
  }
}""",
        "azure_cli": (
            "az security contact create"
            " --name default"
            " --email security@example.com"
            " --phone '+1-555-0100'"
            " --alert-notifications on"
            " --alerts-to-admins on"
        ),
        "description": (
            "Configure a security contact email in Microsoft Defender "
            "for Cloud so that high-severity alerts are sent to the "
            "security team."
        ),
    },
    # ── Subscription – security contact alerts ───────────────────────
    "CIS-AZ-111": {
        "terraform": """resource "azurerm_security_center_contact" "@@tf_name@@" {
  email               = "security@example.com"
  alert_notifications = true
  alerts_to_admins    = true
}""",
        "bicep": """resource secContact 'Microsoft.Security/securityContacts@2020-01-01-preview' = {
  name: 'default'
  properties: {
    emails: 'security@example.com'
    alertNotifications: {
      state: 'On'
      minimalSeverity: 'Medium'
    }
    notificationsByRole: {
      state: 'On'
      roles: ['Owner']
    }
  }
}""",
        "azure_cli": (
            "az security contact create"
            " --name default"
            " --email security@example.com"
            " --alert-notifications on"
            " --alerts-to-admins on"
        ),
        "description": (
            "Enable alert notifications on the security contact so "
            "that high-severity findings trigger email alerts to the "
            "designated recipients."
        ),
    },
    # ── Subscription – auto-provisioning ─────────────────────────────
    "CIS-AZ-112": {
        "terraform": """resource "azurerm_security_center_auto_provisioning" "@@tf_name@@" {
  auto_provision = "On"
}""",
        "bicep": """resource autoProvisioning 'Microsoft.Security/autoProvisioningSettings@2017-08-01-preview' = {
  name: 'default'
  properties: {
    autoProvision: 'On'
  }
}""",
        "azure_cli": ("az security auto-provisioning-setting update --name default --auto-provision On"),
        "description": (
            "Enable auto-provisioning of the monitoring agent so that "
            "new VMs are automatically instrumented for Microsoft "
            "Defender for Cloud."
        ),
    },
    # ── Subscription – max 3 owners ──────────────────────────────────
    "CIS-AZ-113": {
        "terraform": """# Review and remove excess Owner role assignments.
# Use `azurerm_role_assignment` to manage:
resource "azurerm_role_assignment" "owner" {
  scope                = "/subscriptions/@@subscription_id@@"
  role_definition_name = "Owner"
  principal_id         = var.primary_owner_object_id
}""",
        "bicep": """// Review Owner role assignments via:
// az role assignment list --role Owner \\
//   --scope /subscriptions/@@subscription_id@@
// Downgrade extra assignments to Contributor.""",
        "azure_cli": (
            "# List current owners:\n"
            "az role assignment list"
            " --role Owner"
            " --scope /subscriptions/@@subscription_id@@"
            " --output table\n"
            "# Remove excess owners:\n"
            "az role assignment delete"
            " --role Owner"
            " --assignee <excess-principal-id>"
            " --scope /subscriptions/@@subscription_id@@"
        ),
        "description": (
            "Ensure the subscription has at most 3 Owner role "
            "assignments. Downgrade excess owners to Contributor or a "
            "custom least-privilege role."
        ),
    },
    # ── Recovery Services Vault – GRS ────────────────────────────────
    "CIS-AZ-114": {
        "terraform": """resource "azurerm_recovery_services_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku                 = "Standard"

  storage_mode_type = "GeoRedundant"
}""",
        "bicep": """resource rsv 'Microsoft.RecoveryServices/vaults@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: {
    redundancySettings: {
      standardTierStorageRedundancy: 'GeoRedundant'
    }
  }
}""",
        "azure_cli": (
            "az backup vault backup-properties set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --backup-storage-redundancy GeoRedundant"
        ),
        "description": (
            "Set the Recovery Services Vault storage redundancy to "
            "GeoRedundant so that backups survive a regional outage. "
            "Must be set before adding backup items."
        ),
    },
    # ── Recovery Services Vault – soft delete ────────────────────────
    "CIS-AZ-115": {
        "terraform": """resource "azurerm_recovery_services_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku                 = "Standard"

  soft_delete_enabled = true
}""",
        "bicep": """resource rsv 'Microsoft.RecoveryServices/vaults@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: {
    securitySettings: {
      softDeleteSettings: {
        softDeleteState: 'Enabled'
        softDeleteRetentionPeriodInDays: 14
      }
    }
  }
}""",
        "azure_cli": (
            "az backup vault backup-properties set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --soft-delete-feature-state Enable"
        ),
        "description": (
            "Enable soft delete on the Recovery Services Vault to allow "
            "recovery of deleted backup data within the retention "
            "period (default 14 days)."
        ),
    },
    # ── Recovery Services Vault – cross-region restore ───────────────
    "CIS-AZ-116": {
        "terraform": """resource "azurerm_recovery_services_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku                 = "Standard"

  storage_mode_type        = "GeoRedundant"
  cross_region_restore_enabled = true
}""",
        "bicep": """resource rsv 'Microsoft.RecoveryServices/vaults@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: {
    redundancySettings: {
      standardTierStorageRedundancy: 'GeoRedundant'
      crossRegionRestore: 'Enabled'
    }
  }
}""",
        "azure_cli": (
            "az backup vault backup-properties set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --backup-storage-redundancy GeoRedundant"
            " --cross-region-restore-flag true"
        ),
        "description": (
            "Enable cross-region restore on the Recovery Services Vault "
            "so that backups can be restored in the paired Azure region "
            "during a regional outage."
        ),
    },
    # ── Recovery Services Vault – public access off ──────────────────
    "CIS-AZ-117": {
        "terraform": """resource "azurerm_recovery_services_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku                 = "Standard"

  public_network_access_enabled = false
}""",
        "bicep": """resource rsv 'Microsoft.RecoveryServices/vaults@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: {
    publicNetworkAccess: 'Disabled'
  }
}""",
        "azure_cli": (
            "az backup vault backup-properties set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --public-network-access Disable"
        ),
        "description": (
            "Disable public network access on the Recovery Services Vault and use private endpoints for backup traffic."
        ),
    },
    # ── Recovery Services Vault – immutability ───────────────────────
    "CIS-AZ-118": {
        "terraform": """resource "azurerm_recovery_services_vault" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku                 = "Standard"

  immutability = "Unlocked"
}""",
        "bicep": """resource rsv 'Microsoft.RecoveryServices/vaults@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: {
    securitySettings: {
      immutabilitySettings: {
        state: 'Unlocked'
      }
    }
  }
}""",
        "azure_cli": (
            "az backup vault backup-properties set"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --immutability-state Unlocked"
        ),
        "description": (
            "Enable immutability on the Recovery Services Vault to "
            "prevent backup data from being tampered with or deleted "
            "before the retention period ends."
        ),
    },
    # ── SQL DB – geo-redundant backup ────────────────────────────────
    "CIS-AZ-119": {
        "terraform": """resource "azurerm_mssql_database" "@@tf_name@@" {
  name      = "@@name@@"
  server_id = azurerm_mssql_server.example.id
  sku_name  = "S0"

  storage_account_type = "Geo"
}""",
        "bicep": """resource sqlDb 'Microsoft.Sql/servers/databases@2023-02-01-preview' = {
  name: '@@name@@'
  parent: sqlServer
  location: resourceGroup().location
  sku: { name: 'S0' }
  properties: {
    requestedBackupStorageRedundancy: 'Geo'
  }
}""",
        "azure_cli": (
            "az sql db update --name @@name@@"
            " --server @@server_name@@"
            " --resource-group @@resource_group@@"
            " --backup-storage-redundancy Geo"
        ),
        "description": (
            "Set the SQL database backup storage redundancy to Geo "
            "so that point-in-time restore survives a regional outage."
        ),
    },
    # ── Cosmos DB – continuous backup ────────────────────────────────
    "CIS-AZ-120": {
        "terraform": """resource "azurerm_cosmosdb_account" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  backup {
    type = "Continuous"
    tier = "Continuous30Days"
  }

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
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous30Days'
      }
    }
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
            "az cosmosdb update --name @@name@@ --resource-group @@resource_group@@ --backup-policy-type Continuous"
        ),
        "description": (
            "Enable continuous backup on the Cosmos DB account for "
            "point-in-time restore up to 30 days. This is a one-way "
            "migration from periodic backup."
        ),
    },
    # ── Cosmos DB – periodic backup retention ────────────────────────
    "CIS-AZ-121": {
        "terraform": """resource "azurerm_cosmosdb_account" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  backup {
    type                = "Periodic"
    interval_in_minutes = 240
    retention_in_hours  = 168  # 7 days minimum
    storage_redundancy  = "Geo"
  }

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
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: 240
        backupRetentionIntervalInHours: 168
        backupStorageRedundancy: 'Geo'
      }
    }
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
            "az cosmosdb update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --backup-interval 240"
            " --backup-retention 168"
            " --backup-redundancy Geo"
        ),
        "description": (
            "Increase Cosmos DB periodic backup retention to at least "
            "168 hours (7 days) with geo-redundant storage for "
            "disaster recovery."
        ),
    },
    # ── NSG – management ports closed ────────────────────────────────
    "CIS-AZ-122": {
        "terraform": """resource "azurerm_network_security_rule" "deny_mgmt_internet" {
  name                        = "DenyMgmtFromInternet"
  priority                    = 102
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_ranges     = ["139", "445", "5985", "5986"]
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = "@@resource_group@@"
  network_security_group_name = azurerm_network_security_group.example.name
}""",
        "bicep": """resource nsgRule 'Microsoft.Network/networkSecurityGroups/securityRules@2023-04-01' = {
  name: '${nsg.name}/DenyMgmtFromInternet'
  properties: {
    priority: 102
    direction: 'Inbound'
    access: 'Deny'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRanges: ['139', '445', '5985', '5986']
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}""",
        "azure_cli": (
            "az network nsg rule create"
            " --resource-group @@resource_group@@"
            " --nsg-name @@name@@"
            " --name DenyMgmtFromInternet"
            " --priority 102 --direction Inbound --access Deny"
            " --protocol Tcp"
            " --destination-port-ranges 139 445 5985 5986"
            " --source-address-prefixes Internet"
        ),
        "description": (
            "Block inbound SMB, NetBIOS, and WinRM ports from the "
            "internet. Use Azure Bastion or VPN for management access."
        ),
    },
    # ── NSG – database ports closed ──────────────────────────────────
    "CIS-AZ-123": {
        "terraform": """resource "azurerm_network_security_rule" "deny_db_internet" {
  name                        = "DenyDBFromInternet"
  priority                    = 103
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_ranges     = [
    "1433", "3306", "5432", "27017", "6379", "9200"
  ]
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = "@@resource_group@@"
  network_security_group_name = azurerm_network_security_group.example.name
}""",
        "bicep": """resource nsgRule 'Microsoft.Network/networkSecurityGroups/securityRules@2023-04-01' = {
  name: '${nsg.name}/DenyDBFromInternet'
  properties: {
    priority: 103
    direction: 'Inbound'
    access: 'Deny'
    protocol: 'Tcp'
    sourcePortRange: '*'
    destinationPortRanges: [
      '1433'
      '3306'
      '5432'
      '27017'
      '6379'
      '9200'
    ]
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}""",
        "azure_cli": (
            "az network nsg rule create"
            " --resource-group @@resource_group@@"
            " --nsg-name @@name@@"
            " --name DenyDBFromInternet"
            " --priority 103 --direction Inbound --access Deny"
            " --protocol Tcp"
            " --destination-port-ranges 1433 3306 5432 27017 6379 9200"
            " --source-address-prefixes Internet"
        ),
        "description": (
            "Block inbound database ports (SQL, MySQL, PostgreSQL, "
            "MongoDB, Redis, Elasticsearch) from the internet. Use "
            "private endpoints or VNet service endpoints instead."
        ),
    },
    # ── NSG – no wildcard port ───────────────────────────────────────
    "CIS-AZ-124": {
        "terraform": """resource "azurerm_network_security_rule" "deny_all_internet" {
  name                        = "DenyAllFromInternet"
  priority                    = 4000
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = "@@resource_group@@"
  network_security_group_name = azurerm_network_security_group.example.name
}""",
        "bicep": """resource nsgRule 'Microsoft.Network/networkSecurityGroups/securityRules@2023-04-01' = {
  name: '${nsg.name}/DenyAllFromInternet'
  properties: {
    priority: 4000
    direction: 'Inbound'
    access: 'Deny'
    protocol: '*'
    sourcePortRange: '*'
    destinationPortRange: '*'
    sourceAddressPrefix: 'Internet'
    destinationAddressPrefix: '*'
  }
}""",
        "azure_cli": (
            "az network nsg rule create"
            " --resource-group @@resource_group@@"
            " --nsg-name @@name@@"
            " --name DenyAllFromInternet"
            " --priority 4000 --direction Inbound --access Deny"
            " --protocol '*'"
            " --destination-port-ranges '*'"
            " --source-address-prefixes Internet"
        ),
        "description": (
            "Replace wildcard any-port allow rules with explicit "
            "per-port rules. Add a catch-all deny at low priority to "
            "block unexpected inbound traffic from the internet."
        ),
    },
    # ── Public IP – Standard SKU ─────────────────────────────────────
    "CIS-AZ-125": {
        "terraform": """resource "azurerm_public_ip" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  allocation_method   = "Static"
  sku                 = "Standard"
}""",
        "bicep": """resource publicIp 'Microsoft.Network/publicIPAddresses@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: { name: 'Standard' }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}""",
        "azure_cli": (
            "# Basic SKU cannot be upgraded in place. Recreate:\n"
            "az network public-ip create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --sku Standard --allocation-method Static"
        ),
        "description": (
            "Recreate the public IP with Standard SKU. Basic SKU is "
            "deprecated (retirement Sept 2025) and lacks zone "
            "redundancy and DDoS Standard support."
        ),
    },
    # ── Public IP – not orphan ───────────────────────────────────────
    "CIS-AZ-126": {
        "terraform": """# Orphan public IPs should be deleted or attached.
# If no longer needed:
# removed from Terraform state and Azure:
# terraform state rm azurerm_public_ip.orphan
# az network public-ip delete ...""",
        "bicep": """// Orphan public IPs should be deleted if unused.
// az network public-ip delete --name @@name@@ \\
//   --resource-group @@resource_group@@""",
        "azure_cli": (
            "# Delete orphan public IP:\n"
            "az network public-ip delete"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
        ),
        "description": (
            "Delete the orphan public IP if it is no longer needed, "
            "or attach it to the intended resource. Orphan public IPs "
            "waste budget and can be hijacked."
        ),
    },
    # ── Azure Firewall – threat intel deny ───────────────────────────
    "CIS-AZ-127": {
        "terraform": """resource "azurerm_firewall" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  sku_name            = "AZFW_VNet"
  sku_tier            = "Standard"

  threat_intel_mode = "Deny"

  ip_configuration {
    name                 = "fw-ip-config"
    subnet_id            = azurerm_subnet.fw.id
    public_ip_address_id = azurerm_public_ip.fw.id
  }
}""",
        "bicep": """resource firewall 'Microsoft.Network/azureFirewalls@2023-04-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  properties: {
    sku: {
      name: 'AZFW_VNet'
      tier: 'Standard'
    }
    threatIntelMode: 'Deny'
  }
}""",
        "azure_cli": (
            "az network firewall update --name @@name@@ --resource-group @@resource_group@@ --threat-intel-mode Deny"
        ),
        "description": (
            "Set Azure Firewall threat intelligence mode to Deny so "
            "that traffic from/to known-malicious IPs and domains is "
            "actively blocked, not just logged."
        ),
    },
    # ── AKS – authorized IP ranges ───────────────────────────────────
    "CIS-AZ-128": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  api_server_access_profile {
    authorized_ip_ranges = [
      "203.0.113.0/24",
      "198.51.100.0/24",
    ]
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
    apiServerAccessProfile: {
      authorizedIPRanges: [
        '203.0.113.0/24'
        '198.51.100.0/24'
      ]
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
            "az aks update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --api-server-authorized-ip-ranges"
            " 203.0.113.0/24,198.51.100.0/24"
        ),
        "description": (
            "Restrict AKS API server access to an explicit list of "
            "authorized IP ranges for CI/CD runners, bastion hosts, "
            "and admin workstations."
        ),
    },
    # ── AKS – managed identity ───────────────────────────────────────
    "CIS-AZ-129": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  identity {
    type = "SystemAssigned"
  }

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_D2_v2"
  }
}""",
        "bicep": """resource aksCluster 'Microsoft.ContainerService/managedClusters@2023-06-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  identity: { type: 'SystemAssigned' }
  properties: {
    dnsPrefix: 'example'
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
        "azure_cli": ("az aks update --name @@name@@ --resource-group @@resource_group@@ --enable-managed-identity"),
        "description": (
            "Migrate the AKS cluster to use a managed identity instead "
            "of a service principal so that credentials are rotated "
            "automatically by Azure."
        ),
    },
    # ── AKS – Azure Policy add-on ────────────────────────────────────
    "CIS-AZ-130": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  azure_policy_enabled = true

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
    addonProfiles: {
      azurepolicy: {
        enabled: true
      }
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
        "azure_cli": ("az aks enable-addons --name @@name@@ --resource-group @@resource_group@@ --addons azure-policy"),
        "description": (
            "Enable the Azure Policy add-on on the AKS cluster so that "
            "Kubernetes workloads are evaluated against built-in and "
            "custom policy initiatives."
        ),
    },
    # ── AKS – Workload Identity + OIDC ───────────────────────────────
    "CIS-AZ-131": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

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
    oidcIssuerProfile: { enabled: true }
    securityProfile: {
      workloadIdentity: { enabled: true }
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
            "az aks update --name @@name@@"
            " --resource-group @@resource_group@@"
            " --enable-oidc-issuer"
            " --enable-workload-identity"
        ),
        "description": (
            "Enable Workload Identity and the OIDC issuer on the AKS "
            "cluster so that pods can authenticate to Azure resources "
            "using federated identity instead of static secrets."
        ),
    },
    # ── AKS – local accounts disabled ────────────────────────────────
    "CIS-AZ-132": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  local_account_disabled = true

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
    disableLocalAccounts: true
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
        "azure_cli": ("az aks update --name @@name@@ --resource-group @@resource_group@@ --disable-local-accounts"),
        "description": (
            "Disable local admin accounts on the AKS cluster so that "
            "only Azure AD identities can access the cluster via "
            "kubectl."
        ),
    },
    # ── AKS – Azure RBAC for K8s ────────────────────────────────────
    "CIS-AZ-133": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

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
            "az aks update --name @@name@@ --resource-group @@resource_group@@ --enable-aad --enable-azure-rbac"
        ),
        "description": (
            "Enable Azure RBAC for Kubernetes on the AKS cluster so "
            "that authorization decisions use Azure role assignments "
            "instead of native Kubernetes ClusterRoleBindings."
        ),
    },
    # ── AKS – auto-upgrade channel ───────────────────────────────────
    "CIS-AZ-134": {
        "terraform": """resource "azurerm_kubernetes_cluster" "@@tf_name@@" {
  name                = "@@name@@"
  location            = "@@location@@"
  resource_group_name = "@@resource_group@@"
  dns_prefix          = "example"

  automatic_upgrade_channel = "patch"

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
    autoUpgradeProfile: {
      upgradeChannel: 'patch'
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
        "azure_cli": ("az aks update --name @@name@@ --resource-group @@resource_group@@ --auto-upgrade-channel patch"),
        "description": (
            "Set the AKS cluster auto-upgrade channel to 'patch' or "
            "'stable' so that Kubernetes security patches are applied "
            "automatically."
        ),
    },
    # ── PostgreSQL – public access off ───────────────────────────────
    "CIS-AZ-141": {
        "terraform": """resource "azurerm_postgresql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "14"
  sku_name            = "GP_Standard_D2s_v3"
  storage_mb          = 32768

  public_network_access_enabled = false

  delegated_subnet_id = azurerm_subnet.pg.id
  private_dns_zone_id = azurerm_private_dns_zone.pg.id
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
    publicNetworkAccess: 'Disabled'
    network: {
      delegatedSubnetResourceId: subnet.id
      privateDnsZoneArmResourceId: privateDnsZone.id
    }
    storage: { storageSizeGB: 32 }
  }
}""",
        "azure_cli": (
            "az postgres flexible-server update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --public-access Disabled"
        ),
        "description": (
            "Disable public network access on the PostgreSQL flexible "
            "server. Use VNet integration or private endpoints for "
            "connectivity."
        ),
    },
    # ── PostgreSQL – minimum TLS 1.2 ─────────────────────────────────
    "CIS-AZ-142": {
        "terraform": """resource "azurerm_postgresql_flexible_server_configuration" "ssl_min" {
  name      = "ssl_min_protocol_version"
  server_id = azurerm_postgresql_flexible_server.example.id
  value     = "TLSv1.2"
}""",
        "bicep": """resource sslMinVersion 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2022-12-01' = {
  parent: pgServer
  name: 'ssl_min_protocol_version'
  properties: {
    value: 'TLSv1.2'
    source: 'user-override'
  }
}""",
        "azure_cli": (
            "az postgres flexible-server parameter set"
            " --resource-group @@resource_group@@"
            " --server-name @@name@@"
            " --name ssl_min_protocol_version --value TLSv1.2"
        ),
        "description": (
            "Set the minimum TLS protocol version to 1.2 on the "
            "PostgreSQL flexible server to prevent downgrade attacks."
        ),
    },
    # ── PostgreSQL – geo-redundant backup ────────────────────────────
    "CIS-AZ-143": {
        "terraform": """resource "azurerm_postgresql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "14"
  sku_name            = "GP_Standard_D2s_v3"
  storage_mb          = 32768

  backup_retention_days        = 14
  geo_redundant_backup_enabled = true
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
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Enabled'
    }
    storage: { storageSizeGB: 32 }
  }
}""",
        "azure_cli": (
            "# Geo-redundant backup must be set at server creation:\n"
            "az postgres flexible-server create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --geo-redundant-backup Enabled"
            " --backup-retention 14"
        ),
        "description": (
            "Enable geo-redundant backup on the PostgreSQL flexible "
            "server so that point-in-time restore survives a regional "
            "outage. Must be set at creation time."
        ),
    },
    # ── PostgreSQL – backup retention >= 7 days ──────────────────────
    "CIS-AZ-144": {
        "terraform": """resource "azurerm_postgresql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "14"
  sku_name            = "GP_Standard_D2s_v3"
  storage_mb          = 32768

  backup_retention_days = 7
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
    backup: {
      backupRetentionDays: 7
    }
    storage: { storageSizeGB: 32 }
  }
}""",
        "azure_cli": (
            "az postgres flexible-server update"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --backup-retention 7"
        ),
        "description": (
            "Set PostgreSQL flexible server backup retention to at least 7 days for adequate recovery flexibility."
        ),
    },
    # ── MySQL – geo-redundant backup ─────────────────────────────────
    "CIS-AZ-145": {
        "terraform": """resource "azurerm_mysql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "8.0.21"
  sku_name            = "GP_Standard_D2ds_v4"

  backup_retention_days        = 14
  geo_redundant_backup_enabled = true

  storage {
    size_gb = 32
  }
}""",
        "bicep": """resource mysqlServer 'Microsoft.DBforMySQL/flexibleServers@2022-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: {
    name: 'Standard_D2ds_v4'
    tier: 'GeneralPurpose'
  }
  properties: {
    version: '8.0.21'
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Enabled'
    }
    storage: { storageSizeGB: 32 }
  }
}""",
        "azure_cli": (
            "# Geo-redundant backup must be set at server creation:\n"
            "az mysql flexible-server create"
            " --name @@name@@"
            " --resource-group @@resource_group@@"
            " --location @@location@@"
            " --geo-redundant-backup Enabled"
            " --backup-retention 14"
        ),
        "description": (
            "Enable geo-redundant backup on the MySQL flexible server "
            "so that point-in-time restore survives a regional outage. "
            "Must be set at creation time."
        ),
    },
    # ── MySQL – backup retention >= 7 days ───────────────────────────
    "CIS-AZ-146": {
        "terraform": """resource "azurerm_mysql_flexible_server" "@@tf_name@@" {
  name                = "@@name@@"
  resource_group_name = "@@resource_group@@"
  location            = "@@location@@"
  version             = "8.0.21"
  sku_name            = "GP_Standard_D2ds_v4"

  backup_retention_days = 7

  storage {
    size_gb = 32
  }
}""",
        "bicep": """resource mysqlServer 'Microsoft.DBforMySQL/flexibleServers@2022-01-01' = {
  name: '@@name@@'
  location: resourceGroup().location
  sku: {
    name: 'Standard_D2ds_v4'
    tier: 'GeneralPurpose'
  }
  properties: {
    version: '8.0.21'
    backup: {
      backupRetentionDays: 7
    }
    storage: { storageSizeGB: 32 }
  }
}""",
        "azure_cli": (
            "az mysql flexible-server update --name @@name@@ --resource-group @@resource_group@@ --backup-retention 7"
        ),
        "description": (
            "Set MySQL flexible server backup retention to at least 7 days for adequate recovery flexibility."
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
