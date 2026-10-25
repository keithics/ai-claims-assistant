output "id" {
  value       = azurerm_api_management.this.id
  description = "API Management resource ID."
}

output "name" {
  value       = azurerm_api_management.this.name
  description = "API Management service name."
}

output "gateway_url" {
  value       = azurerm_api_management.this.gateway_url
  description = "Gateway base URL. Apps call this, never a model endpoint."
}

output "principal_id" {
  value       = azurerm_api_management.this.identity[0].principal_id
  description = "Principal ID of the gateway's managed identity."
}

output "public_ip_addresses" {
  value       = azurerm_api_management.this.public_ip_addresses
  description = "Outbound and inbound public IPs of the gateway. Use them to restrict the claims API's ingress to the gateway."
}

output "api_paths" {
  value = {
    small      = "${azurerm_api_management.this.gateway_url}/small"
    large      = "${azurerm_api_management.this.gateway_url}/large"
    embeddings = "${azurerm_api_management.this.gateway_url}/embeddings"
    claims     = var.claims_api_url == null ? null : "${azurerm_api_management.this.gateway_url}/claims-api"
  }
  description = "Base URL of each gateway API."
}

output "models_key_secret_names" {
  value       = { for c, s in azurerm_key_vault_secret.models_key : c => s.name }
  description = "Key Vault secret name holding each country's model subscription key."
}

output "claims_key_secret_name" {
  value       = var.claims_api_url == null ? null : azurerm_key_vault_secret.claims_key["claims"].name
  description = "Key Vault secret name holding the claims API subscription key, or null without a claims API."
}

output "models_key_secret_ids" {
  value       = { for c, s in azurerm_key_vault_secret.models_key : c => s.versionless_id }
  description = "Versionless Key Vault secret ID of each country's model subscription key, for apps that read them as secrets."
}

output "claims_key_secret_id" {
  value       = var.claims_api_url == null ? null : azurerm_key_vault_secret.claims_key["claims"].versionless_id
  description = "Versionless Key Vault secret ID of the claims API subscription key, or null without a claims API."
}
