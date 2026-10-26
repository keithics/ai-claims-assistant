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

locals {
  rai_policies = var.content_filter.enabled ? { main = true } : {}

  harm_categories = ["Hate", "Sexual", "SelfHarm", "Violence"]
  filter_rules = concat(
    flatten([
      for category in local.harm_categories : [
        for source in ["Prompt", "Completion"] : {
          name      = category
          source    = source
          threshold = var.content_filter.severity_threshold
        }
      ]
    ]),
    [
      { name = "Jailbreak", source = "Prompt", threshold = var.content_filter.prompt_shield_level },
      { name = "Indirect Attack", source = "Prompt", threshold = var.content_filter.prompt_shield_level },
    ],
  )
}

resource "azurerm_cognitive_account_rai_policy" "this" {
  for_each = local.rai_policies

  name                 = "claims-assistant-filter"
  cognitive_account_id = azurerm_cognitive_account.this.id
  base_policy_name     = var.content_filter.base_policy_name
  mode                 = "Blocking"
  tags                 = var.tags

  dynamic "content_filter" {
    for_each = { for r in local.filter_rules : "${r.name}-${r.source}" => r }

    content {
      name               = content_filter.value.name
      source             = content_filter.value.source
      filter_enabled     = true
      block_enabled      = true
      severity_threshold = content_filter.value.threshold
    }
  }
}

resource "azurerm_cognitive_deployment" "this" {
  for_each = var.deployments

  name                 = each.key
  cognitive_account_id = azurerm_cognitive_account.this.id
  rai_policy_name      = each.value.content_filter && var.content_filter.enabled ? azurerm_cognitive_account_rai_policy.this["main"].name : null

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
