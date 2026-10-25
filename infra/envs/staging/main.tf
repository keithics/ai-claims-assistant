resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

module "naming" {
  source = "../../modules/naming"

  project_name  = var.project_name
  env           = "staging"
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
}
