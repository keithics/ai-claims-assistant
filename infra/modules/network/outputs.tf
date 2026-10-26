output "vnet_id" {
  value       = azurerm_virtual_network.this.id
  description = "Virtual network ID."
}

output "subnet_ids" {
  value       = { for name, subnet in azurerm_subnet.this : name => subnet.id }
  description = "Subnet IDs by name."
}

output "private_dns_zone_ids" {
  value       = { for name, zone in azurerm_private_dns_zone.this : name => zone.id }
  description = "Private DNS zone IDs by zone name."
}
