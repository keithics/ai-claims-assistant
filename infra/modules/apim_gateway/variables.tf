variable "name" {
  type        = string
  description = "API Management service name. Globally unique, 1 to 50 characters."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,48}[a-z0-9]$", var.name))
    error_message = "name must be 2 to 50 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "name_prefix" {
  type        = string
  description = "Name prefix from the naming module, used in product and subscription display names."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the gateway."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "sku_name" {
  type        = string
  description = "API Management SKU as tier_units. Must be a tier that supports llm-token-limit, so Consumption is not allowed. Developer is the cheapest and has no SLA (ADR-001)."
  default     = "Developer_1"

  validation {
    condition     = contains(["Developer_1", "Basic_1", "BasicV2_1", "Standard_1", "StandardV2_1", "Premium_1", "PremiumV2_1"], var.sku_name)
    error_message = "sku_name must be one of Developer_1, Basic_1, BasicV2_1, Standard_1, StandardV2_1, Premium_1, PremiumV2_1. Consumption has no llm-token-limit policy."
  }
}

variable "publisher_name" {
  type        = string
  description = "Publisher name shown by API Management."
}

variable "publisher_email" {
  type        = string
  description = "Publisher email. Set it in the env's terraform.tfvars, never in a module."
}

variable "policies_dir" {
  type        = string
  description = "Directory with the policy templates, normally components/gateway/policies. Passed in by the env."

  validation {
    condition     = length(trimspace(var.policies_dir)) > 0
    error_message = "policies_dir must not be empty."
  }
}

variable "countries" {
  type = map(object({
    tokens_per_minute  = number
    token_quota        = number
    token_quota_period = optional(string, "Monthly")
  }))
  description = "One product and subscription per country, with that country's token limit."

  validation {
    condition     = length(var.countries) > 0 && alltrue([for c in keys(var.countries) : contains(["ph", "sg", "id", "th", "jp"], c)])
    error_message = "countries needs at least one key, each one of ph, sg, id, th, jp."
  }

  validation {
    condition     = alltrue([for c in values(var.countries) : c.tokens_per_minute > 0 && c.token_quota > 0])
    error_message = "tokens_per_minute and token_quota must be greater than 0."
  }

  validation {
    condition     = alltrue([for c in values(var.countries) : contains(["Hourly", "Daily", "Weekly", "Monthly", "Yearly"], c.token_quota_period)])
    error_message = "token_quota_period must be Hourly, Daily, Weekly, Monthly or Yearly."
  }
}

variable "ai_services_id" {
  type        = string
  description = "AI Services account the gateway calls. The gateway identity gets Cognitive Services OpenAI User on it."
}

variable "openai_endpoint" {
  type        = string
  description = "Azure OpenAI endpoint of that account, for example https://name.openai.azure.com/."

  validation {
    condition     = can(regex("^https://", var.openai_endpoint))
    error_message = "openai_endpoint must start with https://."
  }
}

variable "model_deployments" {
  type = object({
    small     = list(string)
    large     = string
    embedding = string
  })
  description = "Deployment names behind the gateway. At least two small deployments form the failover pool."

  validation {
    condition     = length(var.model_deployments.small) >= 2
    error_message = "model_deployments.small needs at least two deployments for failover."
  }
}

variable "claims_api_url" {
  type        = string
  description = "Base URL of the mock claims API. Null skips the claims API, backend and product."
  default     = null
}

variable "application_insights_id" {
  type        = string
  description = "Application Insights resource ID that receives gateway logs and token metrics."
}

variable "application_insights_connection_string" {
  type        = string
  description = "Application Insights connection string for the gateway logger."
  sensitive   = true
}

variable "key_vault_id" {
  type        = string
  description = "Key Vault that receives the subscription keys as secrets. The caller needs a role that can write secrets."
}

variable "restrict_to_cloudflare" {
  type        = bool
  description = "Accept only Cloudflare's IPv4 ranges. Turn off only for tests."
  default     = true
}

variable "extra_allowed_addresses" {
  type        = list(string)
  description = "Extra single IPs allowed through the same filter, for example the outbound IP of callers that do not come through Cloudflare."
  default     = []

  validation {
    condition     = alltrue([for a in var.extra_allowed_addresses : can(regex("^\\d{1,3}(\\.\\d{1,3}){3}$", a))])
    error_message = "extra_allowed_addresses must be IPv4 addresses such as 20.1.2.3."
  }
}

variable "personal_data_headers" {
  type        = list(string)
  description = "Request headers removed before anything is forwarded."
  default = [
    "x-user-id",
    "x-user-email",
    "x-user-name",
    "x-user-phone",
    "x-policy-number",
    "x-claimant-name",
    "x-forwarded-for",
    "x-real-ip",
    "true-client-ip",
    "cf-connecting-ip",
    "cf-connecting-ipv6",
    "cf-ipcountry",
    "cf-access-authenticated-user-email",
    "cf-access-jwt-assertion",
  ]
}

variable "allowed_apps" {
  type        = list(string)
  description = "Values of x-app that are kept as the app dimension; anything else becomes unknown."
  default     = ["agent_app", "evals", "ingest"]
}

variable "allowed_languages" {
  type        = list(string)
  description = "Values of x-language that partition the semantic cache. Anything else is treated as unknown and never cached."
  default     = ["en", "fil", "ceb", "id", "th", "ja"]
}

variable "allowed_route_tiers" {
  type        = list(string)
  description = "Values of x-route-tier that are kept as the route_tier dimension."
  default     = ["small", "large"]
}

variable "metric_namespace" {
  type        = string
  description = "Namespace of the token metrics in Azure Monitor."
  default     = "kalayaan"
}

variable "retry_count" {
  type        = number
  description = "Retries after a 429 or 503 from a model backend. Each retry can land on the other pool member."
  default     = 2

  validation {
    condition     = var.retry_count >= 0 && var.retry_count <= 5
    error_message = "retry_count must be between 0 and 5."
  }
}

variable "circuit_breaker_trip_minutes" {
  type        = number
  description = "How long a backend that returned 429 is skipped. A Retry-After from the backend overrides it. Whole minutes, because API Management reports the duration that way."
  default     = 1

  validation {
    condition     = var.circuit_breaker_trip_minutes >= 1 && var.circuit_breaker_trip_minutes <= 60 && floor(var.circuit_breaker_trip_minutes) == var.circuit_breaker_trip_minutes
    error_message = "circuit_breaker_trip_minutes must be a whole number between 1 and 60."
  }
}

variable "circuit_breaker_failure_count" {
  type        = number
  description = "Backend 429s within 10 seconds that take a deployment out of the pool. One is too touchy: a single burst would empty the whole pool."
  default     = 3

  validation {
    condition     = var.circuit_breaker_failure_count >= 1 && var.circuit_breaker_failure_count <= 100
    error_message = "circuit_breaker_failure_count must be between 1 and 100."
  }
}

variable "max_concurrent_per_country" {
  type        = number
  description = "Requests in flight per country at the model APIs. More get 429 at the gateway, before they can trip the shared backends."
  default     = 8

  validation {
    condition     = var.max_concurrent_per_country >= 1
    error_message = "max_concurrent_per_country must be at least 1."
  }
}

variable "claims_calls_per_minute" {
  type        = number
  description = "Calls per minute per subscription to the claims API."
  default     = 120

  validation {
    condition     = var.claims_calls_per_minute > 0
    error_message = "claims_calls_per_minute must be greater than 0."
  }
}

variable "semantic_cache_enabled" {
  type        = bool
  description = "Semantic cache for the FAQ route. Off by default because it needs Azure Managed Redis with the RediSearch module, which bills by the hour. Turning it on creates the cache, registers it with API Management and adds the lookup and store policies."
  default     = false
}

variable "redis_sku_name" {
  type        = string
  description = "Azure Managed Redis SKU for the semantic cache. The smallest Balanced size is enough for FAQ answers."
  default     = "Balanced_B0"
}

variable "semantic_cache_threshold" {
  type        = string
  description = "Score threshold; lower needs a closer match. Above 0.2 risks wrong cache hits."
  default     = "0.05"
}

variable "semantic_cache_ttl_seconds" {
  type        = number
  description = "How long cached answers live."
  default     = 3600
}
