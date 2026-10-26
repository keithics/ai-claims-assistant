variable "name" {
  type        = string
  description = "AI Services account name from the naming module. Also the default custom subdomain, so it must be globally unique."
}

variable "project_name" {
  type        = string
  description = "Foundry project name from the naming module."
}

variable "location" {
  type        = string
  description = "Azure region for the account."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the account."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "custom_subdomain_name" {
  type        = string
  description = "Custom subdomain (required for Entra auth). Null uses the account name."
  default     = null
}

variable "deployments" {
  type = map(object({
    model_name     = string
    model_version  = string
    model_format   = optional(string, "OpenAI")
    sku_name       = optional(string, "GlobalStandard")
    capacity       = optional(number, 10)
    content_filter = optional(bool, true)
  }))
  description = "Model deployments keyed by deployment name. Pay-as-you-go only; capacity is in thousands of tokens per minute."

  validation {
    condition     = length(var.deployments) > 0
    error_message = "At least one deployment is required."
  }

  validation {
    condition     = alltrue([for d in values(var.deployments) : contains(["Standard", "GlobalStandard", "DataZoneStandard"], d.sku_name)])
    error_message = "sku_name must be Standard, GlobalStandard or DataZoneStandard. Provisioned throughput is not allowed."
  }

  validation {
    condition     = alltrue([for d in values(var.deployments) : d.capacity > 0 && d.capacity <= 100])
    error_message = "capacity must be between 1 and 100 to keep spend small."
  }
}

variable "content_filter" {
  type = object({
    enabled             = optional(bool, true)
    base_policy_name    = optional(string, "Microsoft.DefaultV2")
    severity_threshold  = optional(string, "Medium")
    prompt_shield_level = optional(string, "High")
  })
  description = "Content filter policy attached to the chat deployments: harm categories on prompts and completions, plus the Jailbreak and Indirect Attack prompt shields. Embedding deployments are not filtered."
  default     = {}

  validation {
    condition     = contains(["Low", "Medium", "High"], var.content_filter.severity_threshold) && contains(["Low", "Medium", "High"], var.content_filter.prompt_shield_level)
    error_message = "severity_threshold and prompt_shield_level must be Low, Medium or High."
  }
}

variable "public_network_access_enabled" {
  type        = bool
  description = "Allow public network access. Set false when private networking is on."
  default     = true
}

variable "role_assignments" {
  type = map(object({
    principal_id = string
    role         = string
  }))
  description = "Role assignments on the account, keyed by a stable name."
  default     = {}

  validation {
    condition = alltrue([
      for a in values(var.role_assignments) :
      contains(["Cognitive Services OpenAI User", "Cognitive Services User", "Cognitive Services OpenAI Contributor"], a.role)
    ])
    error_message = "role must be Cognitive Services OpenAI User, Cognitive Services User or Cognitive Services OpenAI Contributor."
  }
}
