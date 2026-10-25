locals {
  function_name = "func-${var.name_prefix}"
  roles = {
    storage   = { scope = var.storage_account_id, role = "Storage Blob Data Owner" }
    logs      = { scope = var.log_analytics_workspace_id, role = "Log Analytics Reader" }
    telemetry = { scope = var.application_insights_id, role = "Monitoring Metrics Publisher" }
  }
}

resource "azurerm_storage_container" "package" {
  name                  = "function-package"
  storage_account_id    = var.storage_account_id
  container_access_type = "private"
}

resource "azurerm_service_plan" "this" {
  name                = "asp-${var.name_prefix}-budget"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = var.tags
}

resource "azurerm_function_app_flex_consumption" "this" {
  name                = local.function_name
  location            = var.location
  resource_group_name = var.resource_group_name
  service_plan_id     = azurerm_service_plan.this.id
  tags                = var.tags

  runtime_name           = "python"
  runtime_version        = var.python_version
  maximum_instance_count = var.maximum_instance_count
  instance_memory_in_mb  = 2048

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${trimsuffix(var.storage_blob_endpoint, "/")}/${azurerm_storage_container.package.name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.this.id
  zip_deploy_file                   = var.package_path

  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  site_config {
    application_insights_connection_string = var.application_insights_connection_string
  }

  app_settings = {
    LOG_ANALYTICS_WORKSPACE_ID = var.log_analytics_workspace_guid
    BUDGET_STATE_ACCOUNT_URL   = trimsuffix(var.storage_blob_endpoint, "/")
    BUDGET_STATE_CONTAINER     = var.state_container_name
    SPEND_QUERY_PATH           = "/home/site/wwwroot/kql/spend_by_country.kql"
    COUNTRY_PACKS_DIR          = "/home/site/wwwroot/country_packs"
    APP_ENV                    = "dev"
    AZURE_CLIENT_ID            = azurerm_user_assigned_identity.this.client_id
  }

  depends_on = [azurerm_role_assignment.this]
}

# A user-assigned identity, so the roles exist before the function app first touches storage.
resource "azurerm_role_assignment" "this" {
  for_each = local.roles

  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_user_assigned_identity" "this" {
  name                = "id-${var.name_prefix}-budget"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "state_changed" {
  name                 = "alert-${var.name_prefix}-budget-state"
  display_name         = "Country budget state changed"
  description          = "A country moved between ok, warn and exceeded."
  location             = var.location
  resource_group_name  = var.resource_group_name
  scopes               = [var.log_analytics_workspace_id]
  severity             = var.alert_severity
  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      AppDependencies
      | where Name == "budget_state_changed"
      | extend country = tostring(Properties["country"]),
               previous_state = tostring(Properties["previous_state"]),
               budget_state = tostring(Properties["budget_state"]),
               spend_usd = todouble(Properties["spend_usd"])
      | project TimeGenerated, country, previous_state, budget_state, spend_usd
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [var.action_group_id]
  }
}
