locals {
  is_free = var.sku == "free"
}

resource "azurerm_search_service" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = var.sku
  replica_count                 = local.is_free ? null : var.replica_count
  partition_count               = local.is_free ? null : var.partition_count
  local_authentication_enabled  = var.local_authentication_enabled
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags
}

resource "azurerm_role_assignment" "this" {
  for_each = var.role_assignments

  scope                = azurerm_search_service.this.id
  role_definition_name = each.value.role
  principal_id         = each.value.principal_id
}
