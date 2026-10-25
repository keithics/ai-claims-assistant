locals {
  action_group_short_name = substr(replace(var.name_prefix, "-", ""), 0, 12)
  workbooks               = var.enable_workbook ? { dashboard = var.workbook_template_path } : {}
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  daily_quota_gb      = var.daily_cap_gb
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                         = "appi-${var.name_prefix}"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  workspace_id                 = azurerm_log_analytics_workspace.this.id
  application_type             = "web"
  daily_data_cap_in_gb         = var.daily_cap_gb
  local_authentication_enabled = var.local_authentication_enabled
  tags                         = var.tags
}

resource "azurerm_monitor_action_group" "this" {
  name                = "ag-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  short_name          = local.action_group_short_name
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = { for i, e in var.action_group_emails : "receiver-${i}" => e }

    content {
      name                    = email_receiver.key
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }
}

resource "azurerm_application_insights_workbook" "this" {
  for_each = local.workbooks

  name                = uuidv5("dns", "workbook-${var.name_prefix}-${each.key}")
  location            = var.location
  resource_group_name = var.resource_group_name
  display_name        = "Claims assistant ${each.key}"
  source_id           = lower(azurerm_application_insights.this.id)
  data_json           = templatefile(each.value, { workspace_id = azurerm_log_analytics_workspace.this.id })
  tags                = var.tags
}
