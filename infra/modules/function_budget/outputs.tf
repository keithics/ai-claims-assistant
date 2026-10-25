output "function_name" {
  value       = azurerm_function_app_flex_consumption.this.name
  description = "Function app name, for deploying the package."
}

output "principal_id" {
  value       = azurerm_user_assigned_identity.this.principal_id
  description = "Principal ID of the function's identity."
}

output "alert_rule_id" {
  value       = azurerm_monitor_scheduled_query_rules_alert_v2.state_changed.id
  description = "Alert rule that fires when a country's budget state changes."
}
