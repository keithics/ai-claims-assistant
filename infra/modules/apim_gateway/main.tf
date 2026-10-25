locals {
  openai_base = trimsuffix(var.openai_endpoint, "/")

  model_backends = toset(distinct(concat(var.model_deployments.small, [var.model_deployments.large, var.model_deployments.embedding])))

  pool_name = "small-pool"

  model_apis = {
    small = {
      backend_id = local.pool_name
      operation  = { id = "chat-completions", display = "Chat completions", url = "/chat/completions" }
    }
    large = {
      backend_id = var.model_deployments.large
      operation  = { id = "chat-completions", display = "Chat completions", url = "/chat/completions" }
    }
    embeddings = {
      backend_id = var.model_deployments.embedding
      operation  = { id = "embeddings", display = "Embeddings", url = "/embeddings" }
    }
  }

  claims_enabled = var.claims_api_url == null ? {} : { claims = true }

  claims_operations = {
    get-claim   = { method = "GET", url = "/claims/{id}", display = "Get a claim", has_id = true }
    draft-claim = { method = "POST", url = "/claims", display = "Create a draft claim", has_id = false }
    file-claim  = { method = "POST", url = "/claims/{id}/file", display = "File an approved claim", has_id = true }
  }

  country_codes   = sort(keys(var.countries))
  allowed_models  = sort(distinct(concat(var.model_deployments.small, [var.model_deployments.large, var.model_deployments.embedding])))
  cloudflare_ips  = file("${var.policies_dir}/cloudflare-ips.xml")
  policy_template = { for name in ["service", "product", "model-api", "claims-api"] : name => "${var.policies_dir}/${name}.xml.tftpl" }
}

resource "azurerm_api_management" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  publisher_name      = var.publisher_name
  publisher_email     = var.publisher_email
  sku_name            = var.sku_name
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "openai_user" {
  scope                = var.ai_services_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_api_management.this.identity[0].principal_id
}

resource "azurerm_api_management_logger" "app_insights" {
  name                = "appinsights"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  resource_id         = var.application_insights_id

  application_insights {
    connection_string = var.application_insights_connection_string
  }
}

# azurerm_api_management_diagnostic has no `metrics` argument, and llm-emit-token-metric needs it on.
resource "azapi_resource" "diagnostic" {
  type      = "Microsoft.ApiManagement/service/diagnostics@2024-05-01"
  name      = "applicationinsights"
  parent_id = azurerm_api_management.this.id

  body = {
    properties = {
      loggerId    = azurerm_api_management_logger.app_insights.id
      alwaysLog   = "allErrors"
      logClientIp = false
      metrics     = true
      verbosity   = "error"
      sampling = {
        samplingType = "fixed"
        percentage   = 100
      }
    }
  }
}

resource "azurerm_api_management_backend" "model" {
  for_each = local.model_backends

  name                = each.key
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  protocol            = "http"
  url                 = "${local.openai_base}/openai/deployments/${each.key}"

  circuit_breaker_rule {
    name                       = "rate-limited"
    trip_duration              = "PT${var.circuit_breaker_trip_minutes}M"
    accept_retry_after_enabled = true

    failure_condition {
      count             = var.circuit_breaker_failure_count
      interval_duration = "PT10S"

      status_code_range {
        min = 429
        max = 429
      }
    }
  }
}

# azurerm has no backend of type Pool; the pool is what gives failover between the small deployments.
resource "azapi_resource" "small_pool" {
  type      = "Microsoft.ApiManagement/service/backends@2024-05-01"
  name      = local.pool_name
  parent_id = azurerm_api_management.this.id

  body = {
    properties = {
      description = "Small-model deployments, round robin with failover"
      type        = "Pool"
      pool = {
        services = [
          for name in var.model_deployments.small : {
            id       = azurerm_api_management_backend.model[name].id
            priority = 1
            weight   = 1
          }
        ]
      }
    }
  }
}

locals {
  semantic_cache = var.semantic_cache_enabled ? { main = true } : {}
}

# The cache looks answers up by embedding the prompt, so it needs its own backend that points at
# the embeddings operation itself (the model APIs append the operation path instead).
resource "azurerm_api_management_backend" "embeddings_cache" {
  for_each = local.semantic_cache

  name                = "embeddings-cache"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  protocol            = "http"
  url                 = "${local.openai_base}/openai/deployments/${var.model_deployments.embedding}/embeddings"
}

resource "azurerm_managed_redis" "cache" {
  for_each = local.semantic_cache

  name                = "redis-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = var.redis_sku_name
  tags                = var.tags

  default_database {
    clustering_policy = "EnterpriseCluster"
    eviction_policy   = "NoEviction"

    module {
      name = "RediSearch"
    }
  }
}

resource "azurerm_api_management_redis_cache" "this" {
  for_each = local.semantic_cache

  name              = "semantic-cache"
  api_management_id = azurerm_api_management.this.id
  cache_location    = "default"
  connection_string = "${azurerm_managed_redis.cache[each.key].hostname}:10000,password=${azurerm_managed_redis.cache[each.key].default_database[0].primary_access_key},ssl=True,abortConnect=False"
}

resource "azurerm_api_management_backend" "claims" {
  for_each = local.claims_enabled

  name                = "claims-api"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  protocol            = "http"
  url                 = trimsuffix(var.claims_api_url, "/")
}

resource "azurerm_api_management_policy" "service" {
  api_management_id = azurerm_api_management.this.id

  xml_content = templatefile(local.policy_template["service"], {
    restrict_to_cloudflare  = var.restrict_to_cloudflare
    cloudflare_ips          = local.cloudflare_ips
    extra_allowed_addresses = var.extra_allowed_addresses
    personal_data_headers   = var.personal_data_headers
  })
}

resource "azurerm_api_management_api" "model" {
  for_each = local.model_apis

  name                  = "models-${each.key}"
  display_name          = "Models (${each.key})"
  api_management_name   = azurerm_api_management.this.name
  resource_group_name   = var.resource_group_name
  revision              = "1"
  path                  = each.key
  protocols             = ["https"]
  subscription_required = true

  subscription_key_parameter_names {
    header = "api-key"
    query  = "subscription-key"
  }
}

resource "azurerm_api_management_api_operation" "model" {
  for_each = local.model_apis

  operation_id        = each.value.operation.id
  api_name            = azurerm_api_management_api.model[each.key].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  display_name        = each.value.operation.display
  method              = "POST"
  url_template        = each.value.operation.url
}

resource "azurerm_api_management_api_policy" "model" {
  for_each = local.model_apis

  api_name            = azurerm_api_management_api.model[each.key].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile(local.policy_template["model-api"], {
    allowed_countries           = local.country_codes
    allowed_apps                = var.allowed_apps
    allowed_models              = local.allowed_models
    allowed_route_tiers         = var.allowed_route_tiers
    metric_namespace            = var.metric_namespace
    semantic_cache_enabled      = var.semantic_cache_enabled
    semantic_cache_threshold    = var.semantic_cache_threshold
    semantic_cache_max_messages = 3
    semantic_cache_ttl_seconds  = var.semantic_cache_ttl_seconds
    embeddings_backend_id       = var.semantic_cache_enabled ? azurerm_api_management_backend.embeddings_cache["main"].name : var.model_deployments.embedding
    model_backend_id            = each.value.backend_id
    retry_count                 = var.retry_count
    max_concurrent_per_country  = var.max_concurrent_per_country
  })

  depends_on = [azapi_resource.small_pool, azurerm_api_management_backend.model, azapi_resource.diagnostic, azurerm_api_management_redis_cache.this]
}

resource "azurerm_api_management_product" "models" {
  for_each = var.countries

  product_id            = "models-${each.key}"
  display_name          = "${var.name_prefix} models ${upper(each.key)}"
  api_management_name   = azurerm_api_management.this.name
  resource_group_name   = var.resource_group_name
  subscription_required = true
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "models" {
  for_each = {
    for pair in setproduct(keys(var.countries), keys(local.model_apis)) : "${pair[0]}-${pair[1]}" => {
      country = pair[0]
      api     = pair[1]
    }
  }

  product_id          = azurerm_api_management_product.models[each.value.country].product_id
  api_name            = azurerm_api_management_api.model[each.value.api].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
}

resource "azurerm_api_management_product_policy" "models" {
  for_each = var.countries

  product_id          = azurerm_api_management_product.models[each.key].product_id
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile(local.policy_template["product"], {
    country            = each.key
    tokens_per_minute  = each.value.tokens_per_minute
    token_quota        = each.value.token_quota
    token_quota_period = each.value.token_quota_period
  })
}

resource "azurerm_api_management_subscription" "models" {
  for_each = var.countries

  display_name        = "${var.name_prefix} models ${upper(each.key)}"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  product_id          = azurerm_api_management_product.models[each.key].id
  state               = "active"
}

resource "azurerm_key_vault_secret" "models_key" {
  for_each = var.countries

  name         = "apim-models-key-${each.key}"
  value        = azurerm_api_management_subscription.models[each.key].primary_key
  key_vault_id = var.key_vault_id
  tags         = var.tags
}

resource "azurerm_api_management_api" "claims" {
  for_each = local.claims_enabled

  name                  = "claims"
  display_name          = "Claims API"
  api_management_name   = azurerm_api_management.this.name
  resource_group_name   = var.resource_group_name
  revision              = "1"
  path                  = "claims-api"
  protocols             = ["https"]
  subscription_required = true

  subscription_key_parameter_names {
    header = "api-key"
    query  = "subscription-key"
  }
}

resource "azurerm_api_management_api_operation" "claims" {
  for_each = var.claims_api_url == null ? {} : local.claims_operations

  operation_id        = each.key
  api_name            = azurerm_api_management_api.claims["claims"].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  display_name        = each.value.display
  method              = each.value.method
  url_template        = each.value.url

  dynamic "template_parameter" {
    for_each = each.value.has_id ? { id = true } : {}

    content {
      name     = template_parameter.key
      required = true
      type     = "string"
    }
  }
}

resource "azurerm_api_management_api_policy" "claims" {
  for_each = local.claims_enabled

  api_name            = azurerm_api_management_api.claims[each.key].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name

  xml_content = templatefile(local.policy_template["claims-api"], {
    allowed_countries = local.country_codes
    calls_per_minute  = var.claims_calls_per_minute
    claims_backend_id = azurerm_api_management_backend.claims[each.key].name
  })
}

resource "azurerm_api_management_product" "claims" {
  for_each = local.claims_enabled

  product_id            = "claims"
  display_name          = "Claims API"
  api_management_name   = azurerm_api_management.this.name
  resource_group_name   = var.resource_group_name
  subscription_required = true
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "claims" {
  for_each = local.claims_enabled

  product_id          = azurerm_api_management_product.claims[each.key].product_id
  api_name            = azurerm_api_management_api.claims[each.key].name
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
}

resource "azurerm_api_management_subscription" "claims" {
  for_each = local.claims_enabled

  display_name        = "Claims API"
  api_management_name = azurerm_api_management.this.name
  resource_group_name = var.resource_group_name
  product_id          = azurerm_api_management_product.claims[each.key].id
  state               = "active"
}

resource "azurerm_key_vault_secret" "claims_key" {
  for_each = local.claims_enabled

  name         = "apim-claims-key"
  value        = azurerm_api_management_subscription.claims[each.key].primary_key
  key_vault_id = var.key_vault_id
  tags         = var.tags
}
