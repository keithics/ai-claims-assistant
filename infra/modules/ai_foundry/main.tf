resource "azurerm_cognitive_account" "this" {
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "AIServices"
  sku_name                      = "S0"
  custom_subdomain_name         = coalesce(var.custom_subdomain_name, var.name)
  local_auth_enabled            = false
  public_network_access_enabled = var.public_network_access_enabled
  project_management_enabled    = true
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_account_project" "this" {
  name                 = var.project_name
  location             = var.location
  cognitive_account_id = azurerm_cognitive_account.this.id
  tags                 = var.tags

  identity {
    type = "SystemAssigned"
  }

  depends_on = [azurerm_cognitive_deployment.this]
}

resource "azurerm_cognitive_deployment" "this" {
  for_each = var.deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = each.value.model_format
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

resource "azurerm_role_assignment" "this" {
  for_each = var.role_assignments

  scope                = azurerm_cognitive_account.this.id
  role_definition_name = each.value.role
  principal_id         = each.value.principal_id
}
