resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

module "naming" {
  source = "../../modules/naming"

  project_name  = var.project_name
  env           = "dev"
  owner         = var.owner
  cost_center   = var.cost_center
  unique_suffix = random_string.suffix.result
}

resource "azurerm_resource_group" "main" {
  name     = module.naming.names.resource_group
  location = var.location
  tags     = module.naming.tags
}

module "cost_budget" {
  source = "../../modules/cost_budget"

  name_prefix         = module.naming.name_prefix
  resource_group_id   = azurerm_resource_group.main.id
  monthly_budget_usd  = var.monthly_budget_usd
  budget_alert_emails = var.budget_alert_emails
  action_group_id     = module.observability.action_group_id
}

module "observability" {
  source = "../../modules/observability"

  name_prefix         = module.naming.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  action_group_emails = var.budget_alert_emails
  retention_days      = var.log_retention_days
  daily_cap_gb        = var.daily_cap_gb

  enable_workbook        = var.enable_workbook
  workbook_template_path = "${path.module}/../../../components/telemetry/workbook/dashboard.workbook.json"
}

data "azurerm_client_config" "current" {}

module "keyvault" {
  source = "../../modules/keyvault"

  name                = module.naming.names.key_vault
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  tenant_id           = data.azurerm_client_config.current.tenant_id

  role_assignments = {
    deployer = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Key Vault Secrets Officer"
    }
  }
}

module "storage" {
  source = "../../modules/storage"

  name                = module.naming.names.storage_account
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags

  role_assignments = {
    deployer = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Storage Blob Data Contributor"
    }
  }
}

locals {
  model_catalog = yamldecode(file("${path.module}/${var.models_catalog_path}"))

  model_deployments = {
    for name, d in local.model_catalog.deployments : name => {
      model_name     = d.model
      model_version  = d.version
      capacity       = var.model_capacity[d.tier]
      content_filter = d.tier != "embedding"
    }
  }
}

module "ai_foundry" {
  source = "../../modules/ai_foundry"

  name                = module.naming.names.ai_services
  project_name        = module.naming.names.foundry_project
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  deployments         = local.model_deployments

  role_assignments = {
    deployer = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Cognitive Services OpenAI User"
    }
  }
}

module "ai_search" {
  source = "../../modules/ai_search"

  name                = module.naming.names.search_service
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  sku                 = var.search_sku

  role_assignments = {
    deployer_service = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Search Service Contributor"
    }
    deployer_data = {
      principal_id = data.azurerm_client_config.current.object_id
      role         = "Search Index Data Contributor"
    }
  }
}

locals {
  container_apps = var.enable_container_apps ? { main = true } : {}
}

resource "random_password" "approval_signing_key" {
  for_each = local.container_apps

  length  = 48
  special = false
}

resource "azurerm_key_vault_secret" "approval_signing_key" {
  for_each = local.container_apps

  name         = "approval-signing-key"
  value        = random_password.approval_signing_key[each.key].result
  key_vault_id = module.keyvault.id
  tags         = module.naming.tags
}

module "container_apps" {
  source   = "../../modules/container_apps"
  for_each = local.container_apps

  name_prefix                      = module.naming.name_prefix
  location                         = var.location
  resource_group_name              = azurerm_resource_group.main.name
  tags                             = module.naming.tags
  log_analytics_workspace_id       = module.observability.log_analytics_workspace_id
  images                           = var.container_images
  registry_server                  = var.registry_server
  key_vault_id                     = module.keyvault.id
  approval_signing_key_secret_id   = azurerm_key_vault_secret.approval_signing_key[each.key].versionless_id
  search_service_id                = module.ai_search.id
  application_insights_id          = module.observability.application_insights_id
  gateway_url                      = try(module.apim_gateway["main"].gateway_url, null)
  gateway_key_secret_ids           = try(module.apim_gateway["main"].models_key_secret_ids, {})
  claims_api_url                   = var.apim_claims_api_url == null ? null : try(module.apim_gateway["main"].api_paths.claims, null)
  claims_key_secret_id             = try(module.apim_gateway["main"].claims_key_secret_id, null)
  budget_state_account_url         = trimsuffix(module.storage.blob_endpoint, "/")
  budget_state_storage_id          = module.storage.id
  search_endpoint                  = module.ai_search.endpoint
  allowed_ip_ranges                = var.allowed_ip_ranges
  acknowledge_unrestricted_ingress = var.acknowledge_unrestricted_ingress
}

locals {
  apim = var.enable_apim ? { main = true } : {}
}

module "apim_gateway" {
  source   = "../../modules/apim_gateway"
  for_each = local.apim

  name                                   = "${module.naming.names.api_management}-${random_string.suffix.result}"
  name_prefix                            = module.naming.name_prefix
  location                               = var.location
  resource_group_name                    = azurerm_resource_group.main.name
  tags                                   = module.naming.tags
  sku_name                               = var.apim_sku
  publisher_name                         = var.owner
  publisher_email                        = var.apim_publisher_email
  policies_dir                           = "${path.module}/../../../components/gateway/policies"
  countries                              = var.apim_country_limits
  ai_services_id                         = module.ai_foundry.account_id
  openai_endpoint                        = module.ai_foundry.openai_endpoint
  model_deployments                      = { small = ["small-a", "small-b"], large = "large", embedding = "embedding" }
  claims_api_url                         = var.apim_claims_api_url
  application_insights_id                = module.observability.application_insights_id
  application_insights_connection_string = module.observability.application_insights_connection_string
  key_vault_id                           = module.keyvault.id
  extra_allowed_addresses                = var.apim_extra_allowed_addresses
  semantic_cache_enabled                 = var.enable_semantic_cache

  depends_on = [module.keyvault]
}

locals {
  budget_function = var.enable_budget_function ? { main = true } : {}
}

module "function_budget" {
  source   = "../../modules/function_budget"
  for_each = local.budget_function

  name_prefix                            = module.naming.name_prefix
  location                               = var.location
  resource_group_name                    = azurerm_resource_group.main.name
  tags                                   = module.naming.tags
  storage_account_id                     = module.storage.id
  storage_account_name                   = module.storage.name
  storage_blob_endpoint                  = module.storage.blob_endpoint
  log_analytics_workspace_id             = module.observability.log_analytics_workspace_id
  log_analytics_workspace_guid           = module.observability.log_analytics_workspace_guid
  application_insights_id                = module.observability.application_insights_id
  application_insights_connection_string = module.observability.application_insights_connection_string
  action_group_id                        = module.observability.action_group_id
  package_path                           = var.budget_function_package
}

resource "azurerm_role_assignment" "deployer_telemetry" {
  scope                = module.observability.application_insights_id
  role_definition_name = "Monitoring Metrics Publisher"
  principal_id         = data.azurerm_client_config.current.object_id
}
