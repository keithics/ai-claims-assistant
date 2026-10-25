output "resource_group_name" {
  value       = azurerm_resource_group.main.name
  description = "Env resource group."
}

output "budget_id" {
  value       = module.cost_budget.budget_id
  description = "Resource group budget ID."
}

output "budget_amount_usd" {
  value       = module.cost_budget.budget_amount_usd
  description = "Monthly budget in USD."
}

output "log_analytics_workspace_id" {
  value       = module.observability.log_analytics_workspace_id
  description = "Log Analytics workspace ID."
}

output "action_group_id" {
  value       = module.observability.action_group_id
  description = "Action group ID."
}

output "application_insights_connection_string" {
  value       = module.observability.application_insights_connection_string
  description = "Application Insights connection string."
  sensitive   = true
}
