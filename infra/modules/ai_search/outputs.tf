output "id" {
  value       = azurerm_search_service.this.id
  description = "Search service resource ID."
}

output "name" {
  value       = azurerm_search_service.this.name
  description = "Search service name."
}

output "endpoint" {
  value       = "https://${azurerm_search_service.this.name}.search.windows.net"
  description = "Search service endpoint."
}
