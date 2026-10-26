variable "name_prefix" {
  type        = string
  description = "Name prefix from the naming module."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the environment and apps."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Workspace that receives the apps' console logs."
}

variable "images" {
  type = object({
    agent_app  = string
    claims_api = string
    web_ui     = string
  })
  description = "Full image references (registry/name:tag), one per app. Built with make build C=<app>."

  validation {
    condition     = alltrue([for image in values(var.images) : length(trimspace(image)) > 0])
    error_message = "Every image reference must be non-empty."
  }
}

variable "registry_server" {
  type        = string
  description = "Private registry host (for example an ACR login server). Null means public images. The apps pull with their own identities, so the caller grants AcrPull to the principal IDs in the identities output."
  default     = null
}

variable "key_vault_id" {
  type        = string
  description = "Key Vault that holds the approval signing key. The app identities get the Secrets User role on it."
}

variable "approval_signing_key_secret_id" {
  type        = string
  description = "Versionless Key Vault secret ID of the approval signing key shared by agent_app and claims_api."
}

variable "search_service_id" {
  type        = string
  description = "AI Search service the agent app reads (Search Index Data Reader)."
}

variable "application_insights_id" {
  type        = string
  description = "Application Insights the agent app sends telemetry to (Monitoring Metrics Publisher)."
}

variable "gateway_url" {
  type        = string
  description = "API Management gateway URL. The app reaches every model and embedding through it, never a model endpoint."

  validation {
    condition     = can(regex("^https://", var.gateway_url)) && !can(regex("\\.(openai|cognitiveservices)\\.azure\\.com|\\.services\\.ai\\.azure\\.com", var.gateway_url))
    error_message = "gateway_url must be an https URL of the gateway, not a model endpoint."
  }
}

variable "gateway_key_secret_ids" {
  type        = map(string)
  description = "Versionless Key Vault secret ID of each country's gateway subscription key, keyed by country code. Becomes GATEWAY_KEY_<COUNTRY> in agent_app."

  validation {
    condition     = length(var.gateway_key_secret_ids) > 0 && alltrue([for c in keys(var.gateway_key_secret_ids) : contains(["ph", "sg", "id", "th", "jp"], c)])
    error_message = "gateway_key_secret_ids needs at least one key, each one of ph, sg, id, th, jp."
  }
}

variable "claims_api_url" {
  type        = string
  description = "Claims API URL for agent_app. Null uses the internal claims_api app; set it to the gateway's claims path to go through the gateway."
  default     = null
}

variable "claims_key_secret_id" {
  type        = string
  description = "Versionless Key Vault secret ID of the claims subscription key, used with a gateway claims_api_url. Becomes GATEWAY_CLAIMS_KEY."
  default     = null
}

variable "search_endpoint" {
  type        = string
  description = "AI Search endpoint."
}

variable "allowed_ip_ranges" {
  type        = list(string)
  description = "CIDR ranges allowed to reach the public apps, normally Cloudflare's published ranges. Everything else is denied."
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_ip_ranges : can(cidrnetmask(cidr))])
    error_message = "allowed_ip_ranges must be IPv4 CIDR ranges such as 173.245.48.0/20."
  }
}

variable "acknowledge_unrestricted_ingress" {
  type        = bool
  description = "Must be true to publish the apps without an IP allow list. There is no user sign-in, so anyone could chat, spend tokens and approve claims."
  default     = false
}

variable "min_replicas" {
  type        = map(number)
  description = "Minimum replicas per app. agent_app and claims_api keep state in memory, so they stay at 1 and never scale out."
  default = {
    agent_app  = 1
    claims_api = 1
    web_ui     = 0
  }
}

variable "cpu" {
  type        = number
  description = "vCPU per container."
  default     = 0.25
}

variable "memory" {
  type        = string
  description = "Memory per container."
  default     = "0.5Gi"
}

variable "budget_state_account_url" {
  type        = string
  description = "Blob endpoint of the storage account that holds the budget state. agent_app reads it with Storage Blob Data Reader."
  default     = ""
}

variable "budget_state_storage_id" {
  type        = string
  description = "Resource ID of the storage account that holds the budget state. When set, agent_app gets Storage Blob Data Reader on it."
  default     = ""
}

variable "agent_levers" {
  type        = string
  description = "Comma-separated token levers switched on in agent_app. The measured recommendation is compact_prompts,retrieval_trim (docs/unit-economics.md)."
  default     = "compact_prompts,retrieval_trim"
}

variable "infrastructure_subnet_id" {
  type        = string
  description = "Subnet (at least /23) for the environment when private networking is on. Null keeps the environment on the platform network."
  default     = null
}
