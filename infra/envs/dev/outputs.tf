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

output "key_vault_uri" {
  value       = module.keyvault.vault_uri
  description = "Key Vault URI."
}

output "storage_account_name" {
  value       = module.storage.name
  description = "Storage account for policy documents and eval results."
}

output "ai_services_endpoint" {
  value       = module.ai_foundry.endpoint
  description = "AI Services endpoint."
}

output "model_deployment_names" {
  value       = module.ai_foundry.deployment_names
  description = "Model deployment names."
}

output "search_endpoint" {
  value       = module.ai_search.endpoint
  description = "AI Search endpoint."
}

output "container_app_urls" {
  value       = try(module.container_apps["main"].urls, null)
  description = "URLs of the deployed apps, or null while enable_container_apps is false."
}

output "container_app_identities" {
  value       = try(module.container_apps["main"].identities, null)
  description = "Identities of the deployed apps, for granting AcrPull on a private registry."
}

output "gateway_url" {
  value       = try(module.apim_gateway["main"].gateway_url, null)
  description = "API Management gateway URL, or null while enable_apim is false."
}

output "gateway_api_paths" {
  value       = try(module.apim_gateway["main"].api_paths, null)
  description = "Base URL of each gateway API."
}
