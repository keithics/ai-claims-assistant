output "budget_id" {
  value       = azurerm_consumption_budget_resource_group.this.id
  description = "ID of the resource group budget."
}

output "budget_amount_usd" {
  value       = azurerm_consumption_budget_resource_group.this.amount
  description = "Monthly budget amount in USD."
}
