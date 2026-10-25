mock_provider "azurerm" {
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-test"
      principal_id = "11111111-1111-1111-1111-111111111111"
      client_id    = "22222222-2222-2222-2222-222222222222"
    }
  }

  mock_resource "azurerm_service_plan" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Web/serverFarms/asp-test"
    }
  }

  mock_resource "azurerm_storage_container" {
    defaults = {
      id = "https://sttest.blob.core.windows.net/function-package"
    }
  }
}

variables {
  name_prefix                            = "claims-assistant-dev"
  location                               = "southeastasia"
  resource_group_name                    = "rg-test"
  tags                                   = { project = "claims-assistant" }
  storage_account_id                     = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/sttest"
  storage_account_name                   = "sttest"
  storage_blob_endpoint                  = "https://sttest.blob.core.windows.net/"
  log_analytics_workspace_id             = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.OperationalInsights/workspaces/log-test"
  log_analytics_workspace_guid           = "33333333-3333-3333-3333-333333333333"
  application_insights_id                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Insights/components/appi-test"
  application_insights_connection_string = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
  action_group_id                        = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.Insights/actionGroups/ag-test"
}

run "uses_the_cheapest_plan_and_identity_based_storage" {
  command = plan

  assert {
    condition     = azurerm_service_plan.this.sku_name == "FC1" && azurerm_service_plan.this.os_type == "Linux"
    error_message = "Flex Consumption on Linux is the pay-per-use plan."
  }

  assert {
    condition     = azurerm_function_app_flex_consumption.this.storage_authentication_type == "UserAssignedIdentity" && azurerm_function_app_flex_consumption.this.storage_access_key == null
    error_message = "Storage access must use the managed identity, not a key."
  }
}

run "identity_has_only_three_narrow_roles" {
  command = plan

  assert {
    condition     = toset([for r in azurerm_role_assignment.this : r.role_definition_name]) == toset(["Storage Blob Data Owner", "Log Analytics Reader", "Monitoring Metrics Publisher"]) && length(azurerm_role_assignment.this) == 3
    error_message = "Expected exactly the three roles the function needs."
  }

  assert {
    condition     = azurerm_role_assignment.this["logs"].scope == var.log_analytics_workspace_id && azurerm_role_assignment.this["storage"].scope == var.storage_account_id
    error_message = "Each role must be scoped to its own resource."
  }
}

run "app_settings_point_at_the_state_store_and_the_spend_query" {
  command = apply

  assert {
    condition     = azurerm_function_app_flex_consumption.this.app_settings["BUDGET_STATE_ACCOUNT_URL"] == "https://sttest.blob.core.windows.net" && azurerm_function_app_flex_consumption.this.app_settings["BUDGET_STATE_CONTAINER"] == "budget-state" && azurerm_function_app_flex_consumption.this.app_settings["LOG_ANALYTICS_WORKSPACE_ID"] == "33333333-3333-3333-3333-333333333333"
    error_message = "The function needs the state account, container and workspace GUID."
  }

  assert {
    condition     = !contains([for k, v in azurerm_function_app_flex_consumption.this.app_settings : k], "AzureWebJobsStorage") && !strcontains(join(",", values(azurerm_function_app_flex_consumption.this.app_settings)), "AccountKey")
    error_message = "No storage keys in app settings."
  }
}

run "alert_fires_on_state_changes_and_notifies_the_action_group" {
  command = plan

  assert {
    condition     = strcontains(azurerm_monitor_scheduled_query_rules_alert_v2.state_changed.criteria[0].query, "budget_state_changed") && azurerm_monitor_scheduled_query_rules_alert_v2.state_changed.evaluation_frequency == "PT15M" && azurerm_monitor_scheduled_query_rules_alert_v2.state_changed.criteria[0].threshold == 0
    error_message = "The alert must count budget_state_changed spans every 15 minutes."
  }

  assert {
    condition     = azurerm_monitor_scheduled_query_rules_alert_v2.state_changed.action[0].action_groups[0] == var.action_group_id
    error_message = "The alert must notify the observability action group."
  }
}

run "package_deployment_is_optional_and_used_when_given" {
  command = plan

  variables {
    package_path = "dist/budget_controller.zip"
  }

  assert {
    condition     = azurerm_function_app_flex_consumption.this.zip_deploy_file == "dist/budget_controller.zip" && var.package_path != null
    error_message = "A given package must be deployed."
  }
}

run "rejects_a_bad_instance_limit" {
  command = plan

  variables {
    maximum_instance_count = 5
  }

  expect_failures = [var.maximum_instance_count]
}
