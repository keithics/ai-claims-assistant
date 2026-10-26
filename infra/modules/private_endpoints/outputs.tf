output "endpoint_ids" {
  value       = { for name, endpoint in azurerm_private_endpoint.this : name => endpoint.id }
  description = "Private endpoint IDs by name."
}
