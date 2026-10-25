mock_provider "azurerm" {
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-test"
      principal_id = "11111111-1111-1111-1111-111111111111"
      client_id    = "22222222-2222-2222-2222-222222222222"
    }
  }

  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id             = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/Microsoft.App/managedEnvironments/cae-test"
      default_domain = "happyfield-1234.southeastasia.azurecontainerapps.io"
    }
  }
}

variables {
  name_prefix                    = "claims-assistant-dev"
  location                       = "southeastasia"
  resource_group_name            = "rg-test"
  tags                           = { project = "claims-assistant" }
  log_analytics_workspace_id     = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/log"
  images                         = { agent_app = "ghcr.io/example/agent_app:1", claims_api = "ghcr.io/example/claims_api:1", web_ui = "ghcr.io/example/web_ui:1" }
  key_vault_id                   = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
  approval_signing_key_secret_id = "https://kv.vault.azure.net/secrets/approval-signing-key"
  search_service_id              = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Search/searchServices/s"
  application_insights_id        = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Insights/components/ai"
  gateway_url                    = "https://apim-test.azure-api.net"
  gateway_key_secret_ids         = { ph = "https://kv.vault.azure.net/secrets/apim-models-key-ph", th = "https://kv.vault.azure.net/secrets/apim-models-key-th" }
  search_endpoint                = "https://srch.search.windows.net"
  allowed_ip_ranges              = ["173.245.48.0/20", "103.21.244.0/22"]
}

run "public_apps_are_restricted_and_claims_api_is_internal" {
  command = plan

  assert {
    condition     = azurerm_container_app.this["agent_app"].ingress[0].external_enabled && azurerm_container_app.this["web_ui"].ingress[0].external_enabled && !azurerm_container_app.this["claims_api"].ingress[0].external_enabled
    error_message = "agent_app and web_ui must be public, claims_api internal"
  }

  assert {
    condition     = length(azurerm_container_app.this["agent_app"].ingress[0].ip_security_restriction) == 2 && length(azurerm_container_app.this["web_ui"].ingress[0].ip_security_restriction) == 2
    error_message = "public apps must carry the allow list"
  }

  assert {
    condition     = length(azurerm_container_app.this["claims_api"].ingress[0].ip_security_restriction) == 0
    error_message = "the internal app has no public allow list"
  }

  assert {
    condition     = alltrue([for r in azurerm_container_app.this["agent_app"].ingress[0].ip_security_restriction : r.action == "Allow"])
    error_message = "restrictions must be Allow rules"
  }
}

run "app_names_fit_the_32_character_limit_even_for_long_prefixes" {
  command = plan

  variables {
    name_prefix = "claims-assistant-staging-jp"
  }

  assert {
    condition     = alltrue([for a in azurerm_container_app.this : length(a.name) <= 32 && !endswith(a.name, "-") && !strcontains(a.name, "--")])
    error_message = "container app names must be at most 32 characters, with no trailing or double hyphen"
  }

  assert {
    condition     = length(distinct([for a in azurerm_container_app.this : a.name])) == 3
    error_message = "the three app names must stay distinct"
  }
}

run "stateful_apps_run_a_single_replica" {
  command = plan

  assert {
    condition     = azurerm_container_app.this["agent_app"].template[0].min_replicas == 1 && azurerm_container_app.this["agent_app"].template[0].max_replicas == 1 && azurerm_container_app.this["claims_api"].template[0].max_replicas == 1
    error_message = "agent_app and claims_api keep state in memory and must not scale out"
  }

  assert {
    condition     = azurerm_container_app.this["web_ui"].template[0].min_replicas == 0
    error_message = "web_ui may scale to zero"
  }
}

run "signing_key_comes_from_key_vault_for_the_two_python_apps_only" {
  command = plan

  assert {
    condition     = length([for x in azurerm_container_app.this["agent_app"].secret : x.name if x.name == "approval-signing-key"]) == 1 && length(azurerm_container_app.this["claims_api"].secret) == 1 && length(azurerm_container_app.this["web_ui"].secret) == 0
    error_message = "only agent_app and claims_api get the signing key secret"
  }

  assert {
    condition     = contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "APPROVAL_SIGNING_KEY") && !contains([for e in azurerm_container_app.this["web_ui"].template[0].container[0].env : e.name], "APPROVAL_SIGNING_KEY")
    error_message = "the web UI must not receive the signing key"
  }

  assert {
    condition     = alltrue([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.value == null || e.name != "APPROVAL_SIGNING_KEY"])
    error_message = "the signing key must be a secret reference, not a plain value"
  }
}

run "agent_app_is_wired_to_the_other_apps_and_azure" {
  command = apply

  assert {
    condition     = contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "CLAIMS_API_URL") && contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "AZURE_CLIENT_ID")
    error_message = "agent_app needs the claims URL and its identity's client id"
  }

  assert {
    condition     = strcontains(output.urls["claims_api"], ".internal.")
    error_message = "claims_api URL must be the internal address"
  }

  assert {
    condition     = contains([for e in azurerm_container_app.this["web_ui"].template[0].container[0].env : e.name], "API_BASE_URL")
    error_message = "the web UI gets its API address from the environment at start"
  }
}

run "least_privilege_roles" {
  command = plan

  assert {
    condition     = length([for k, r in azurerm_role_assignment.this : k if startswith(k, "agent_app-")]) == 3 && length([for k, r in azurerm_role_assignment.this : k if startswith(k, "claims_api-")]) == 1
    error_message = "agent_app gets three narrow roles and claims_api only Key Vault Secrets User"
  }

  assert {
    condition     = alltrue([for r in azurerm_role_assignment.this : contains(["Search Index Data Reader", "Monitoring Metrics Publisher", "Key Vault Secrets User"], r.role_definition_name)])
    error_message = "only the three expected roles may be granted; no app gets access to the models"
  }
}

run "private_registry_uses_the_app_identity" {
  command = plan

  variables {
    registry_server = "myregistry.azurecr.io"
  }

  assert {
    condition     = length(azurerm_container_app.this["agent_app"].registry) == 1 && azurerm_container_app.this["agent_app"].registry[0].server == "myregistry.azurecr.io"
    error_message = "registry block missing"
  }
}

run "public_images_need_no_registry" {
  command = plan

  assert {
    condition     = length(azurerm_container_app.this["agent_app"].registry) == 0
    error_message = "no registry block for public images"
  }
}

run "refuses_to_publish_without_an_allow_list" {
  command = plan

  variables {
    allowed_ip_ranges = []
  }

  expect_failures = [azurerm_container_app.this]
}

run "unrestricted_ingress_needs_an_explicit_acknowledgement" {
  command = plan

  variables {
    allowed_ip_ranges                = []
    acknowledge_unrestricted_ingress = true
  }

  assert {
    condition     = length(azurerm_container_app.this["agent_app"].ingress[0].ip_security_restriction) == 0
    error_message = "acknowledged unrestricted ingress should have no rules"
  }
}

run "rejects_a_bad_cidr" {
  command = plan

  variables {
    allowed_ip_ranges = ["not-a-cidr"]
  }

  expect_failures = [var.allowed_ip_ranges]
}

run "rejects_an_empty_image" {
  command = plan

  variables {
    images = { agent_app = "", claims_api = "x", web_ui = "y" }
  }

  expect_failures = [var.images]
}

run "agent_app_reaches_models_only_through_the_gateway_with_country_keys" {
  command = plan

  assert {
    condition     = contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "AGENT_GATEWAY_URL") && contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "GATEWAY_KEY_PH") && contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "GATEWAY_KEY_TH")
    error_message = "agent_app needs the gateway URL and one key per country"
  }

  assert {
    condition     = length([for x in azurerm_container_app.this["agent_app"].secret : x.name if startswith(x.name, "gateway-key-")]) == 2
    error_message = "country keys must come from Key Vault secrets"
  }

  assert {
    condition     = alltrue([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.value == null || !strcontains(e.value, "azure.com")])
    error_message = "no plain env value may point at an Azure endpoint"
  }
}

run "gateway_url_must_not_be_a_model_endpoint" {
  command = plan

  variables {
    gateway_url = "https://ais.openai.azure.com/"
  }

  expect_failures = [var.gateway_url]
}

run "agent_app_can_read_the_budget_state_when_a_store_is_given" {
  command = plan

  variables {
    budget_state_storage_id  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/st"
    budget_state_account_url = "https://st.blob.core.windows.net"
  }

  assert {
    condition     = azurerm_role_assignment.this["agent_app-budget"].role_definition_name == "Storage Blob Data Reader"
    error_message = "agent_app only needs to read the budget state"
  }

  assert {
    condition     = contains([for e in azurerm_container_app.this["agent_app"].template[0].container[0].env : e.name], "BUDGET_STATE_ACCOUNT_URL")
    error_message = "agent_app needs the state account URL"
  }
}
