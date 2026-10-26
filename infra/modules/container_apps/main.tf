locals {
  apps = toset(["agent_app", "claims_api", "web_ui"])

  ports = {
    agent_app  = 8000
    claims_api = 8001
    web_ui     = 80
  }

  max_replicas = {
    agent_app  = 1
    claims_api = 1
    web_ui     = 2
  }

  external = {
    agent_app  = true
    claims_api = false
    web_ui     = true
  }

  gateway_secrets = merge(
    { for country, id in var.gateway_key_secret_ids : "gateway-key-${country}" => id },
    var.claims_key_secret_id == null ? {} : { "gateway-claims-key" = var.claims_key_secret_id },
  )

  restrictions = { for index, cidr in var.allowed_ip_ranges : "allow-${index}" => cidr }

  agent_roles = {
    search    = { scope = var.search_service_id, role = "Search Index Data Reader" }
    telemetry = { scope = var.application_insights_id, role = "Monitoring Metrics Publisher" }
    secrets   = { scope = var.key_vault_id, role = "Key Vault Secrets User" }
  }

  budget_roles = var.budget_state_storage_id == "" ? {} : {
    budget = { scope = var.budget_state_storage_id, role = "Storage Blob Data Reader" }
  }

  claims_roles = {
    secrets = { scope = var.key_vault_id, role = "Key Vault Secrets User" }
  }

  role_assignments = merge(
    { for key, value in merge(local.agent_roles, local.budget_roles) : "agent_app-${key}" => merge(value, { app = "agent_app" }) },
    { for key, value in local.claims_roles : "claims_api-${key}" => merge(value, { app = "claims_api" }) },
  )

  short_names = {
    agent_app  = "agent"
    claims_api = "claims"
    web_ui     = "web"
  }

  app_names = {
    for app in local.apps :
    app => trimsuffix(substr("ca-${local.short_names[app]}-${var.name_prefix}", 0, 32), "-")
  }
  domain = azurerm_container_app_environment.this.default_domain

  urls = {
    agent_app  = "https://${local.app_names["agent_app"]}.${local.domain}"
    web_ui     = "https://${local.app_names["web_ui"]}.${local.domain}"
    claims_api = "https://${local.app_names["claims_api"]}.internal.${local.domain}"
  }
}

resource "azurerm_user_assigned_identity" "this" {
  for_each = local.apps

  name                = "id-${each.key}-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_role_assignment" "this" {
  for_each = local.role_assignments

  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.this[each.value.app].principal_id
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${var.name_prefix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  tags                       = var.tags

  infrastructure_subnet_id = var.infrastructure_subnet_id
}

resource "azurerm_container_app" "this" {
  for_each = local.apps

  name                         = local.app_names[each.key]
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this[each.key].id]
  }

  dynamic "registry" {
    for_each = var.registry_server == null ? [] : [var.registry_server]

    content {
      server   = registry.value
      identity = azurerm_user_assigned_identity.this[each.key].id
    }
  }

  dynamic "secret" {
    for_each = contains(["agent_app", "claims_api"], each.key) ? ["approval-signing-key"] : []

    content {
      name                = secret.value
      key_vault_secret_id = var.approval_signing_key_secret_id
      identity            = azurerm_user_assigned_identity.this[each.key].id
    }
  }

  dynamic "secret" {
    for_each = each.key == "agent_app" ? local.gateway_secrets : {}

    content {
      name                = secret.key
      key_vault_secret_id = secret.value
      identity            = azurerm_user_assigned_identity.this[each.key].id
    }
  }

  ingress {
    external_enabled = local.external[each.key]
    target_port      = local.ports[each.key]
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }

    dynamic "ip_security_restriction" {
      for_each = local.external[each.key] ? local.restrictions : {}

      content {
        name             = ip_security_restriction.key
        action           = "Allow"
        ip_address_range = ip_security_restriction.value
      }
    }
  }

  template {
    min_replicas = var.min_replicas[each.key]
    max_replicas = local.max_replicas[each.key]

    container {
      name   = replace(each.key, "_", "-")
      image  = var.images[each.key]
      cpu    = var.cpu
      memory = var.memory

      dynamic "env" {
        for_each = each.key == "agent_app" ? {
          AGENT_GATEWAY_URL        = var.gateway_url
          RAG_SEARCH_ENDPOINT      = var.search_endpoint
          CLAIMS_API_URL           = coalesce(var.claims_api_url, local.urls["claims_api"])
          AGENT_CORS_ORIGINS       = local.urls["web_ui"]
          BUDGET_STATE_ACCOUNT_URL = var.budget_state_account_url
          AGENT_LEVERS             = var.agent_levers
          AZURE_CLIENT_ID          = azurerm_user_assigned_identity.this["agent_app"].client_id
        } : {}

        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = each.key == "web_ui" ? { API_BASE_URL = local.urls["agent_app"] } : {}

        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = each.key == "agent_app" ? local.gateway_secrets : {}

        content {
          name        = upper(replace(env.key, "-", "_"))
          secret_name = env.key
        }
      }

      dynamic "env" {
        for_each = contains(["agent_app", "claims_api"], each.key) ? ["approval-signing-key"] : []

        content {
          name        = "APPROVAL_SIGNING_KEY"
          secret_name = env.value
        }
      }

      dynamic "liveness_probe" {
        for_each = each.key == "web_ui" ? [] : ["/healthz"]

        content {
          transport = "HTTP"
          port      = local.ports[each.key]
          path      = liveness_probe.value
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = length(var.allowed_ip_ranges) > 0 || var.acknowledge_unrestricted_ingress
      error_message = "Set allowed_ip_ranges (for example Cloudflare's ranges) or, knowing there is no sign-in, acknowledge_unrestricted_ingress = true."
    }
  }

  depends_on = [azurerm_role_assignment.this]
}
