mock_provider "azurerm" {}
mock_provider "azapi" {}

variables {
  name                                   = "apim-test-abc123"
  name_prefix                            = "claims-assistant-dev"
  location                               = "southeastasia"
  resource_group_name                    = "rg-test"
  tags                                   = { project = "claims-assistant" }
  publisher_name                         = "Kalayaan Mutual"
  publisher_email                        = "platform@example.com"
  policies_dir                           = "../../../components/gateway/policies"
  ai_services_id                         = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a"
  openai_endpoint                        = "https://ais-test.openai.azure.com/"
  application_insights_id                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Insights/components/ai"
  application_insights_connection_string = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
  key_vault_id                           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
  model_deployments = {
    small     = ["small-a", "small-b"]
    large     = "large"
    embedding = "embedding"
  }
  countries = {
    ph = { tokens_per_minute = 20000, token_quota = 1000000 }
    th = { tokens_per_minute = 5000, token_quota = 200000, token_quota_period = "Daily" }
  }
}

run "gateway_uses_a_tier_with_token_limits_and_a_managed_identity" {
  command = plan

  assert {
    condition     = azurerm_api_management.this.sku_name == "Developer_1" && azurerm_api_management.this.identity[0].type == "SystemAssigned"
    error_message = "Default tier is Developer_1 with a system-assigned identity."
  }

  assert {
    condition     = azurerm_role_assignment.openai_user.role_definition_name == "Cognitive Services OpenAI User"
    error_message = "Gateway identity must only get Cognitive Services OpenAI User."
  }
}

run "consumption_tier_is_rejected" {
  command = plan

  variables {
    sku_name = "Consumption_0"
  }

  expect_failures = [var.sku_name]
}

run "one_product_and_subscription_per_country_and_keys_go_to_key_vault" {
  command = plan

  assert {
    condition     = toset(keys(azurerm_api_management_product.models)) == toset(["ph", "th"]) && toset(keys(azurerm_api_management_subscription.models)) == toset(["ph", "th"])
    error_message = "Expected a product and a subscription for each country."
  }

  assert {
    condition     = azurerm_key_vault_secret.models_key["ph"].name == "apim-models-key-ph"
    error_message = "Keys must be stored in Key Vault under apim-models-key-<country>."
  }

  assert {
    condition     = length(azurerm_api_management_product_api.models) == 6
    error_message = "Each country product holds the small, large and embeddings APIs."
  }
}

run "each_country_gets_its_own_token_limit_in_the_rendered_policy" {
  command = plan

  assert {
    condition     = strcontains(azurerm_api_management_product_policy.models["ph"].xml_content, "tokens-per-minute=\"20000\"") && strcontains(azurerm_api_management_product_policy.models["ph"].xml_content, "token-quota-period=\"Monthly\"")
    error_message = "PH policy should carry PH's limit."
  }

  assert {
    condition     = strcontains(azurerm_api_management_product_policy.models["th"].xml_content, "tokens-per-minute=\"5000\"") && strcontains(azurerm_api_management_product_policy.models["th"].xml_content, "token-quota-period=\"Daily\"") && strcontains(azurerm_api_management_product_policy.models["th"].xml_content, "!= \"th\"")
    error_message = "TH policy should carry TH's limit and country check."
  }
}

run "service_policy_has_one_ip_filter_with_all_fifteen_cloudflare_ranges" {
  command = plan

  assert {
    condition     = length(regexall("<ip-filter ", azurerm_api_management_policy.service.xml_content)) == 1 && length(regexall("<address-range ", azurerm_api_management_policy.service.xml_content)) == 15
    error_message = "Expected exactly one ip-filter holding the 15 Cloudflare ranges."
  }
}

run "extra_addresses_and_restriction_switch" {
  command = plan

  variables {
    extra_allowed_addresses = ["20.1.2.3"]
  }

  assert {
    condition     = strcontains(azurerm_api_management_policy.service.xml_content, "<address>20.1.2.3</address>") && length(regexall("<ip-filter ", azurerm_api_management_policy.service.xml_content)) == 1
    error_message = "Extra addresses must join the same ip-filter."
  }
}

run "restriction_can_be_turned_off_for_tests" {
  command = plan

  variables {
    restrict_to_cloudflare = false
  }

  assert {
    condition     = !strcontains(azurerm_api_management_policy.service.xml_content, "ip-filter")
    error_message = "No ip-filter expected when restriction is off."
  }
}

run "model_backends_trip_on_429_and_the_pool_holds_the_two_small_ones" {
  command = plan

  assert {
    condition     = toset(keys(azurerm_api_management_backend.model)) == toset(["embedding", "large", "small-a", "small-b"])
    error_message = "One backend per deployment."
  }

  assert {
    condition     = azurerm_api_management_backend.model["small-a"].circuit_breaker_rule[0].failure_condition[0].status_code_range[0].min == 429 && azurerm_api_management_backend.model["small-a"].circuit_breaker_rule[0].accept_retry_after_enabled
    error_message = "Backends must trip on 429 and honour Retry-After."
  }

  assert {
    condition     = azurerm_api_management_backend.model["small-a"].circuit_breaker_rule[0].failure_condition[0].count == 3
    error_message = "A single 429 must not take a deployment out of the pool."
  }

  assert {
    condition     = azurerm_api_management_backend.model["small-a"].url == "https://ais-test.openai.azure.com/openai/deployments/small-a"
    error_message = "Backend URL should include the deployment path."
  }

  assert {
    condition     = length(azapi_resource.small_pool.body.properties.pool.services) == 2
    error_message = "The pool needs both small deployments."
  }
}

run "model_api_policy_points_each_api_at_the_right_backend_and_validates_countries" {
  command = plan

  assert {
    condition     = strcontains(azurerm_api_management_api_policy.model["small"].xml_content, "backend-id=\"small-pool\"") && strcontains(azurerm_api_management_api_policy.model["large"].xml_content, "backend-id=\"large\"") && strcontains(azurerm_api_management_api_policy.model["embeddings"].xml_content, "backend-id=\"embedding\"")
    error_message = "Each API must use its own backend."
  }

  assert {
    condition     = strcontains(azurerm_api_management_api_policy.model["small"].xml_content, "\"ph\", \"th\",")
    error_message = "Allowed countries should be the configured ones."
  }

  assert {
    condition     = !strcontains(azurerm_api_management_api_policy.model["small"].xml_content, "llm-semantic-cache")
    error_message = "Semantic cache is off by default."
  }
}

run "diagnostic_turns_on_custom_metrics_and_does_not_log_client_ips" {
  command = plan

  assert {
    condition     = azapi_resource.diagnostic.body.properties.metrics && !azapi_resource.diagnostic.body.properties.logClientIp
    error_message = "Custom metrics on, client IP logging off."
  }
}

run "claims_api_is_skipped_without_a_url" {
  command = plan

  assert {
    condition     = length(azurerm_api_management_api.claims) == 0 && length(azurerm_api_management_backend.claims) == 0 && length(azurerm_key_vault_secret.claims_key) == 0
    error_message = "No claims API pieces without claims_api_url."
  }
}

run "claims_api_is_added_with_its_own_product_and_key" {
  command = plan

  variables {
    claims_api_url = "https://claims.example.internal/"
  }

  assert {
    condition     = azurerm_api_management_backend.claims["claims"].url == "https://claims.example.internal" && length(azurerm_api_management_api_operation.claims) == 3
    error_message = "Claims backend and its three operations expected."
  }

  assert {
    condition     = azurerm_key_vault_secret.claims_key["claims"].name == "apim-claims-key" && !strcontains(azurerm_api_management_api_policy.claims["claims"].xml_content, "llm-")
    error_message = "Claims key goes to Key Vault and the claims policy has no token policies."
  }
}

run "needs_two_small_deployments" {
  command = plan

  variables {
    model_deployments = {
      small     = ["small-a"]
      large     = "large"
      embedding = "embedding"
    }
  }

  expect_failures = [var.model_deployments]
}

run "country_must_be_a_supported_market" {
  command = plan

  variables {
    countries = { vn = { tokens_per_minute = 1, token_quota = 1 } }
  }

  expect_failures = [var.countries]
}
