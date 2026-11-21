targetScope = 'resourceGroup'

@description('Proposed paid-resource region. Confirm availability, billing and data residency before deployment.')
param location string = 'eastus2'
@minLength(3)
@maxLength(11)
param prefix string = 'labeltrace'
@description('Existing Microsoft Entra PostgreSQL administrator object ID; not an application password.')
param entraAdminObjectId string
param entraAdminName string
@allowed(['User', 'Group', 'ServicePrincipal'])
param entraAdminType string = 'Group'
@description('No Azure AI resources are provisioned by this template. AI stays deterministic.')
param environmentName string = 'poc'

var suffix = uniqueString(resourceGroup().id, prefix)
var apiName = '${prefix}-api-${suffix}'
var storageName = '${prefix}${suffix}'
var postgresName = '${prefix}-pg-${suffix}'
var containerName = 'labeltrace-private'
var tags = { project: 'LabelTrace', environment: environmentName, data: 'synthetic' }

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${prefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.34.0.0/16'] }
    subnets: [
      { name: 'app-service', properties: { addressPrefix: '10.34.1.0/26', delegations: [{ name: 'web', properties: { serviceName: 'Microsoft.Web/serverFarms' } }] } }
      { name: 'postgres', properties: { addressPrefix: '10.34.2.0/27', delegations: [{ name: 'postgres', properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' } }] } }
      { name: 'private-endpoints', properties: { addressPrefix: '10.34.3.0/27', privateEndpointNetworkPolicies: 'Disabled' } }
    ]
  }
}

resource blobDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
  tags: tags
}
resource blobDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: blobDns
  name: '${prefix}-blob-link'
  location: 'global'
  properties: { registrationEnabled: false, virtualNetwork: { id: network.id } }
}
resource postgresDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: '${prefix}.private.postgres.database.azure.com'
  location: 'global'
  tags: tags
}
resource postgresDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: postgresDns
  name: '${prefix}-pg-link'
  location: 'global'
  properties: { registrationEnabled: false, virtualNetwork: { id: network.id } }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    networkAcls: { defaultAction: 'Deny', bypass: 'None' }
  }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: containerName
  properties: { publicAccess: 'None' }
}
resource blobEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${prefix}-blob-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: network.properties.subnets[2].id }
    privateLinkServiceConnections: [{
      name: 'blob'
      properties: { privateLinkServiceId: storage.id, groupIds: ['blob'] }
    }]
  }
}
resource blobZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: blobEndpoint
  name: 'default'
  properties: { privateDnsZoneConfigs: [{ name: 'blob', properties: { privateDnsZoneId: blobDns.id } }] }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  tags: tags
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '17'
    authConfig: { activeDirectoryAuth: 'Enabled', passwordAuth: 'Disabled', tenantId: tenant().tenantId }
    storage: { storageSizeGB: 32, type: 'Premium_LRS', autoGrow: 'Enabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: {
      delegatedSubnetResourceId: network.properties.subnets[1].id
      privateDnsZoneArmResourceId: postgresDns.id
      publicNetworkAccess: 'Disabled'
    }
  }
  dependsOn: [postgresDnsLink]
}
resource admin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: postgres
  name: entraAdminObjectId
  properties: { principalName: entraAdminName, principalType: entraAdminType, tenantId: tenant().tenantId }
}
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'labeltrace'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource staticSite 'Microsoft.Web/staticSites@2024-11-01' = {
  name: '${prefix}-web-${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard', tier: 'Standard' }
  properties: { provider: 'Custom', stagingEnvironmentPolicy: 'Disabled', allowConfigFileUpdates: true }
}
resource plan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: '${prefix}-linux-plan'
  location: location
  tags: tags
  kind: 'linux'
  sku: { name: 'B1', tier: 'Basic', capacity: 1 }
  properties: { reserved: true }
}
resource api 'Microsoft.Web/sites@2024-11-01' = {
  name: apiName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    virtualNetworkSubnetId: network.properties.subnets[0].id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'bash scripts/azure-start.sh'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      healthCheckPath: '/api/health/ready'
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APP_ENV', value: 'production' }
        { name: 'SEED_DEMO', value: '0' }
        { name: 'DATABASE_AUTH', value: 'azure_identity' }
        { name: 'PGHOST', value: postgres.properties.fullyQualifiedDomainName }
        { name: 'PGDATABASE', value: database.name }
        { name: 'PGUSER', value: apiName }
        { name: 'PGSSLROOTCERT', value: 'system' }
        { name: 'STORAGE_BACKEND', value: 'azure' }
        { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
        { name: 'AZURE_STORAGE_CONTAINER', value: containerName }
        { name: 'AZURE_AUTH_MODE', value: 'managed_identity' }
        { name: 'AI_MODE', value: 'deterministic' }
        { name: 'DOCUMENT_EXTRACTOR', value: 'local' }
        { name: 'COOKIE_SECURE', value: '1' }
        { name: 'ALLOWED_ORIGINS', value: 'https://${staticSite.properties.defaultHostname}' }
        { name: 'LABELTRACE_DATA', value: '/tmp/labeltrace' }
        { name: 'WEBSITES_CONTAINER_START_TIME_LIMIT', value: '600' }
        { name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES', value: '3' }
      ]
    }
  }
}
resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: container
  name: guid(container.id, api.id, 'Storage Blob Data Contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: api.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output appServiceName string = api.name
output appServiceResourceId string = api.id
output appServicePrincipalId string = api.identity.principalId
output staticWebAppName string = staticSite.name
output frontendUrl string = 'https://${staticSite.properties.defaultHostname}'
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output postgresDatabase string = database.name
output postgresIdentityRole string = apiName
output storageAccountName string = storage.name
output artifactContainer string = containerName
output nextStep string = 'After approved provisioning: Entra SQL role bootstrap, source deployment, SWA backend link, interactive synthetic-user bootstrap, cloud verification.'
