output "log_analytics_workspace_id" {
  value       = azurerm_log_analytics_workspace.this.id
  description = "Log Analytics workspace resource ID."
}

output "application_insights_id" {
  value       = azurerm_application_insights.this.id
  description = "Application Insights resource ID."
}

output "application_insights_connection_string" {
  value       = azurerm_application_insights.this.connection_string
  description = "Application Insights connection string."
  sensitive   = true
}

output "action_group_id" {
  value       = azurerm_monitor_action_group.this.id
  description = "Action group resource ID, used by the budget and alert rules."
}
