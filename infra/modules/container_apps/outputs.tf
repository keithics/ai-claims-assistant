output "environment_id" {
  value       = azurerm_container_app_environment.this.id
  description = "Container Apps environment ID."
}

output "urls" {
  value       = local.urls
  description = "App URLs. claims_api is internal to the environment."
}

output "identities" {
  value = {
    for app, identity in azurerm_user_assigned_identity.this :
    app => { id = identity.id, principal_id = identity.principal_id, client_id = identity.client_id }
  }
  description = "App identities. Grant AcrPull to these principal IDs when using a private registry."
}
