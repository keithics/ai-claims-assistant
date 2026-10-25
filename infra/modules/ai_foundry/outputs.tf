output "account_id" {
  value       = azurerm_cognitive_account.this.id
  description = "AI Services account resource ID."
}

output "project_id" {
  value       = azurerm_cognitive_account_project.this.id
  description = "Foundry project resource ID."
}

output "endpoint" {
  value       = azurerm_cognitive_account.this.endpoint
  description = "AI Services endpoint."
}

output "openai_endpoint" {
  value       = "https://${coalesce(var.custom_subdomain_name, var.name)}.openai.azure.com/"
  description = "Azure OpenAI endpoint. Only the gateway uses this; apps call the gateway."
}

output "deployment_names" {
  value       = { for k, d in azurerm_cognitive_deployment.this : k => d.name }
  description = "Deployment names by key."
}

output "principal_id" {
  value       = azurerm_cognitive_account.this.identity[0].principal_id
  description = "Principal ID of the account's managed identity."
}
