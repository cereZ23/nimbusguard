"""IaC remediation snippets for CIS Azure controls.

Maps control codes to Terraform, Bicep, and Azure CLI fix suggestions.
"""

from __future__ import annotations

REMEDIATION_SNIPPETS: dict[str, dict[str, str]] = {
    # ── Storage ──────────────────────────────────────────────────────────
    "CIS-AZ-07": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                     = "<storage-account-name>"
  resource_group_name      = azurerm_resource_group.example.name
  location                 = azurerm_resource_group.example.location
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
  name: '<storage-account-name>'
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
        "azure_cli": "az storage account update --name <storage-account> --resource-group <rg> --encryption-key-source Microsoft.Keyvault --encryption-key-vault <vault-uri> --encryption-key-name <key-name>",
        "description": "Enable customer-managed key (CMK) encryption for the storage account using a Key Vault key.",
    },
    "CIS-AZ-09": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                      = "<storage-account-name>"
  resource_group_name       = azurerm_resource_group.example.name
  location                  = azurerm_resource_group.example.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enforce HTTPS-only access
  https_traffic_only_enabled = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '<storage-account-name>'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
  }
}""",
        "azure_cli": "az storage account update --name <storage-account> --resource-group <rg> --https-only true",
        "description": "Enforce HTTPS-only access (secure transfer) on the storage account.",
    },
    "CIS-AZ-11": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                      = "<storage-account-name>"
  resource_group_name       = azurerm_resource_group.example.name
  location                  = azurerm_resource_group.example.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Disable anonymous blob public access
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '<storage-account-name>'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
  }
}""",
        "azure_cli": "az storage account update --name <storage-account> --resource-group <rg> --allow-blob-public-access false",
        "description": "Disable blob public access on the storage account to prevent anonymous reads.",
    },
    "CIS-AZ-72": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                      = "<storage-account-name>"
  resource_group_name       = azurerm_resource_group.example.name
  location                  = azurerm_resource_group.example.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enforce minimum TLS 1.2
  min_tls_version = "TLS1_2"
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '<storage-account-name>'
  location: resourceGroup().location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
  }
}""",
        "azure_cli": "az storage account update --name <storage-account> --resource-group <rg> --min-tls-version TLS1_2",
        "description": "Set the minimum TLS version to 1.2 on the storage account.",
    },
    "CIS-AZ-73": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                      = "<storage-account-name>"
  resource_group_name       = azurerm_resource_group.example.name
  location                  = azurerm_resource_group.example.location
  account_tier              = "Standard"
  account_replication_type  = "LRS"

  # Enable infrastructure (double) encryption
  infrastructure_encryption_enabled = true
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '<storage-account-name>'
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
        "azure_cli": "# Infrastructure encryption must be enabled at storage account creation time.\n# It cannot be toggled after creation. Recreate the account with:\naz storage account create --name <storage-account> --resource-group <rg> --location <location> --sku Standard_LRS --require-infrastructure-encryption true",
        "description": "Enable infrastructure encryption (double encryption) on the storage account. Note: this must be set at creation time.",
    },
    # ── NSG / Network ───────────────────────────────────────────────────
    "CIS-AZ-06": {
        "terraform": """resource "azurerm_network_watcher_flow_log" "example" {
  name                 = "nsg-flow-log"
  network_watcher_name = azurerm_network_watcher.example.name
  resource_group_name  = azurerm_resource_group.example.name

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
        "azure_cli": "az network watcher flow-log create --name <flow-log-name> --nsg <nsg-id> --resource-group <rg> --storage-account <storage-id> --enabled true --retention 90 --workspace <workspace-id>",
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
  resource_group_name         = azurerm_resource_group.example.name
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
        "azure_cli": "az network nsg rule create --resource-group <rg> --nsg-name <nsg> --name DenySSHFromInternet --priority 100 --direction Inbound --access Deny --protocol Tcp --destination-port-ranges 22 --source-address-prefixes Internet",
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
  resource_group_name         = azurerm_resource_group.example.name
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
        "azure_cli": "az network nsg rule create --resource-group <rg> --nsg-name <nsg> --name DenyRDPFromInternet --priority 101 --direction Inbound --access Deny --protocol Tcp --destination-port-ranges 3389 --source-address-prefixes Internet",
        "description": "Deny inbound RDP (port 3389) from the internet by adding a high-priority deny rule to the NSG.",
    },
    # ── Web App / App Service ───────────────────────────────────────────
    "CIS-AZ-10": {
        "terraform": """resource "azurerm_linux_web_app" "example" {
  name                = "<app-name>"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
  service_plan_id     = azurerm_service_plan.example.id

  # Enforce HTTPS only
  https_only = true

  site_config {}
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '<app-name>'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {}
  }
}""",
        "azure_cli": "az webapp update --name <app-name> --resource-group <rg> --set httpsOnly=true",
        "description": "Enforce HTTPS-only access on the web app to redirect all HTTP traffic to HTTPS.",
    },
    "CIS-AZ-23": {
        "terraform": """resource "azurerm_linux_web_app" "example" {
  name                = "<app-name>"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    # Enforce minimum TLS 1.2
    minimum_tls_version = "1.2"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '<app-name>'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      minTlsVersion: '1.2'
    }
  }
}""",
        "azure_cli": "az webapp config set --name <app-name> --resource-group <rg> --min-tls-version 1.2",
        "description": "Set the minimum TLS version to 1.2 for the web app.",
    },
    "CIS-AZ-25": {
        "terraform": """resource "azurerm_linux_web_app" "example" {
  name                = "<app-name>"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
  service_plan_id     = azurerm_service_plan.example.id

  site_config {
    # Disable FTP entirely (or use "FtpsOnly" for FTPS)
    ftps_state = "Disabled"
  }
}""",
        "bicep": """resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '<app-name>'
  location: resourceGroup().location
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      ftpsState: 'Disabled'
    }
  }
}""",
        "azure_cli": "az webapp config set --name <app-name> --resource-group <rg> --ftps-state Disabled",
        "description": "Disable FTP on the web app. Use 'FtpsOnly' if FTPS is needed, or 'Disabled' to block all FTP.",
    },
    # ── Key Vault ───────────────────────────────────────────────────────
    "CIS-AZ-16": {
        "terraform": """resource "azurerm_key_vault" "example" {
  name                = "<vault-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable purge protection (irreversible once enabled)
  purge_protection_enabled = true
  soft_delete_retention_days = 90
}""",
        "bicep": """resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '<vault-name>'
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
        "azure_cli": "az keyvault update --name <vault-name> --resource-group <rg> --enable-purge-protection true",
        "description": "Enable purge protection on the Key Vault. This is irreversible once enabled and prevents permanent deletion during the retention period.",
    },
    "CIS-AZ-17": {
        "terraform": """resource "azurerm_key_vault" "example" {
  name                = "<vault-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Soft delete is enabled by default since 2020-12-15
  # Explicitly set retention period
  soft_delete_retention_days = 90
}""",
        "bicep": """resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '<vault-name>'
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
        "azure_cli": "# Soft delete is enforced by default on new Key Vaults.\n# For older vaults, enable it:\naz keyvault update --name <vault-name> --resource-group <rg> --enable-soft-delete true",
        "description": "Enable soft delete on the Key Vault to allow recovery of deleted keys, secrets, and certificates.",
    },
    "CIS-AZ-21": {
        "terraform": """resource "azurerm_key_vault" "example" {
  name                = "<vault-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
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
  name: '<vault-name>'
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
        "azure_cli": "az keyvault update --name <vault-name> --resource-group <rg> --default-action Deny --bypass AzureServices",
        "description": "Restrict Key Vault network access by setting the default firewall action to Deny and allowing only specific VNets/IPs.",
    },
    # ── SQL Server ──────────────────────────────────────────────────────
    "CIS-AZ-27": {
        "terraform": """resource "azurerm_mssql_server" "example" {
  name                         = "<sql-server-name>"
  resource_group_name          = azurerm_resource_group.example.name
  location                     = azurerm_resource_group.example.location
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = var.sql_admin_password

  # Disable public network access
  public_network_access_enabled = false
}

# Use private endpoint instead
resource "azurerm_private_endpoint" "sql" {
  name                = "pe-sql"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "sql-connection"
    private_connection_resource_id = azurerm_mssql_server.example.id
    subresource_names              = ["sqlServer"]
    is_manual_connection           = false
  }
}""",
        "bicep": """resource sqlServer 'Microsoft.Sql/servers@2023-02-01-preview' = {
  name: '<sql-server-name>'
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
        "azure_cli": "az sql server update --name <sql-server> --resource-group <rg> --enable-public-network false",
        "description": "Disable public network access on the SQL Server and use private endpoints for connectivity.",
    },
    "CIS-AZ-28": {
        "terraform": """resource "azurerm_mssql_server" "example" {
  name                         = "<sql-server-name>"
  resource_group_name          = azurerm_resource_group.example.name
  location                     = azurerm_resource_group.example.location
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = var.sql_admin_password

  # Enforce minimum TLS 1.2
  minimum_tls_version = "1.2"
}""",
        "bicep": """resource sqlServer 'Microsoft.Sql/servers@2023-02-01-preview' = {
  name: '<sql-server-name>'
  location: resourceGroup().location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    version: '12.0'
  }
}""",
        "azure_cli": "az sql server update --name <sql-server> --resource-group <rg> --minimal-tls-version 1.2",
        "description": "Set the minimum TLS version to 1.2 on the SQL Server.",
    },
    # ── Cosmos DB ───────────────────────────────────────────────────────
    "CIS-AZ-35": {
        "terraform": """resource "azurerm_cosmosdb_account" "example" {
  name                = "<cosmosdb-account>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Disable public network access
  public_network_access_enabled = false

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.example.location
    failover_priority = 0
  }
}""",
        "bicep": """resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '<cosmosdb-account>'
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
        "azure_cli": "az cosmosdb update --name <cosmosdb-account> --resource-group <rg> --enable-public-network false",
        "description": "Disable public network access on the Cosmos DB account and use private endpoints.",
    },
    # ── ACR ─────────────────────────────────────────────────────────────
    "CIS-AZ-39": {
        "terraform": """resource "azurerm_container_registry" "example" {
  name                = "<registry-name>"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
  sku                 = "Standard"

  # Disable admin user -- use Azure AD service principal instead
  admin_enabled = false
}""",
        "bicep": """resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: '<registry-name>'
  location: resourceGroup().location
  sku: { name: 'Standard' }
  properties: {
    adminUserEnabled: false
  }
}""",
        "azure_cli": "az acr update --name <registry-name> --resource-group <rg> --admin-enabled false",
        "description": "Disable the admin user on the container registry. Use Azure AD service principals or managed identity for authentication.",
    },
    # ── AKS ─────────────────────────────────────────────────────────────
    "CIS-AZ-41": {
        "terraform": """resource "azurerm_kubernetes_cluster" "example" {
  name                = "<aks-cluster-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
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
  name: '<aks-cluster-name>'
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
        "azure_cli": "# RBAC cannot be enabled on an existing non-RBAC cluster.\n# For new clusters:\naz aks create --name <aks-cluster> --resource-group <rg> --enable-rbac --enable-aad --enable-azure-rbac",
        "description": "Enable Kubernetes RBAC on the AKS cluster with Azure AD integration for centralized access control.",
    },
    "CIS-AZ-42": {
        "terraform": """resource "azurerm_kubernetes_cluster" "example" {
  name                = "<aks-cluster-name>"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
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
  name: '<aks-cluster-name>'
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
        "azure_cli": "# Network policy must be set at cluster creation time:\naz aks create --name <aks-cluster> --resource-group <rg> --network-plugin azure --network-policy calico",
        "description": "Configure a network policy engine (Azure or Calico) on the AKS cluster to control pod-to-pod traffic.",
    },
    # ── Storage soft delete (blob) ──────────────────────────────────────
    "CIS-AZ-75": {
        "terraform": """resource "azurerm_storage_account" "example" {
  name                     = "<storage-account-name>"
  resource_group_name      = azurerm_resource_group.example.name
  location                 = azurerm_resource_group.example.location
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
  name: '<storage-account-name>'
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
        "azure_cli": "az storage account blob-service-properties update --account-name <storage-account> --resource-group <rg> --enable-versioning true --enable-delete-retention true --delete-retention-days 30 --enable-container-delete-retention true --container-delete-retention-days 30",
        "description": "Enable blob versioning and soft delete to protect against accidental deletion.",
    },
    # ── Additional high-value controls ──────────────────────────────────
    "CIS-AZ-15": {
        "terraform": """resource "azurerm_storage_account_network_rules" "example" {
  storage_account_id = azurerm_storage_account.example.id

  default_action = "Deny"
  bypass         = ["AzureServices"]

  virtual_network_subnet_ids = [
    azurerm_subnet.example.id,
  ]

  ip_rules = ["203.0.113.0/24"]
}""",
        "bicep": """resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '<storage-account-name>'
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
        "azure_cli": "az storage account update --name <storage-account> --resource-group <rg> --default-action Deny --bypass AzureServices",
        "description": "Restrict storage account network access to specific VNets and IP ranges.",
    },
    "CIS-AZ-37": {
        "terraform": """resource "azurerm_postgresql_flexible_server" "example" {
  name                = "<pg-server-name>"
  resource_group_name = azurerm_resource_group.example.name
  location            = azurerm_resource_group.example.location
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
  name: '<pg-server-name>'
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
        "azure_cli": "az postgres flexible-server parameter set --resource-group <rg> --server-name <pg-server> --name require_secure_transport --value on",
        "description": "Enforce SSL/TLS connections on the PostgreSQL flexible server.",
    },
    "CIS-AZ-40": {
        "terraform": """resource "azurerm_container_registry" "example" {
  name                          = "<registry-name>"
  resource_group_name           = azurerm_resource_group.example.name
  location                      = azurerm_resource_group.example.location
  sku                           = "Premium"

  # Disable public network access
  public_network_access_enabled = false
}

resource "azurerm_private_endpoint" "acr" {
  name                = "pe-acr"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  subnet_id           = azurerm_subnet.private.id

  private_service_connection {
    name                           = "acr-connection"
    private_connection_resource_id = azurerm_container_registry.example.id
    subresource_names              = ["registry"]
    is_manual_connection           = false
  }
}""",
        "bicep": """resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: '<registry-name>'
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
        "azure_cli": "az acr update --name <registry-name> --resource-group <rg> --public-network-enabled false",
        "description": "Disable public network access on the container registry. Requires Premium SKU and private endpoints.",
    },
    "CIS-AZ-12": {
        "terraform": """resource "azurerm_storage_container" "example" {
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
        "azure_cli": "az storage container set-permission --name <container-name> --account-name <storage-account> --public-access off",
        "description": "Set blob container access level to private (no anonymous access).",
    },
}


def get_remediation_for_control(control_code: str) -> dict[str, str] | None:
    """Return remediation snippets for a given control code, or None if not available."""
    return REMEDIATION_SNIPPETS.get(control_code)
