output "resource_group_name" {
  value       = azurerm_resource_group.state.name
  description = "Resource group holding the state storage."
}

output "storage_account_name" {
  value       = azurerm_storage_account.state.name
  description = "Storage account for Terraform state."
}

output "container_name" {
  value       = azurerm_storage_container.state.name
  description = "Blob container for Terraform state."
}

output "backend_config" {
  value       = <<-EOT
    resource_group_name  = "${azurerm_resource_group.state.name}"
    storage_account_name = "${azurerm_storage_account.state.name}"
    container_name       = "${azurerm_storage_container.state.name}"
    use_azuread_auth     = true
  EOT
  description = "Contents for an env's backend.hcl; add key = \"<env>.tfstate\" per env."
}
