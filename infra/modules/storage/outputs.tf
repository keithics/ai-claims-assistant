output "id" {
  value       = azurerm_storage_account.this.id
  description = "Storage account resource ID."
}

output "name" {
  value       = azurerm_storage_account.this.name
  description = "Storage account name."
}

output "blob_endpoint" {
  value       = azurerm_storage_account.this.primary_blob_endpoint
  description = "Primary blob endpoint."
}

output "container_names" {
  value       = sort([for c in azurerm_storage_container.this : c.name])
  description = "Names of the created containers."
}
