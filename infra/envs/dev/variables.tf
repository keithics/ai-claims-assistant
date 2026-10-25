variable "subscription_id" {
  type        = string
  description = "Azure subscription this env deploys into."
}

variable "project_name" {
  type        = string
  description = "Project name, set once per env."
  default     = "claims-assistant"
}

variable "location" {
  type        = string
  description = "Azure region for the env's resources."
  default     = "southeastasia"
}

variable "owner" {
  type        = string
  description = "Owner tag value."
}

variable "cost_center" {
  type        = string
  description = "Cost center tag value."
}

variable "budget_alert_emails" {
  type        = list(string)
  description = "Recipients of budget alerts and the action group. Set in the gitignored terraform.tfvars."
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly budget for the env's resource group in USD."
  default     = 50
}

variable "log_retention_days" {
  type        = number
  description = "Log Analytics retention in days."
  default     = 30
}

variable "daily_cap_gb" {
  type        = number
  description = "Daily ingestion cap in GB for Log Analytics and Application Insights."
  default     = 1
}

variable "resource_provider_registrations" {
  type        = string
  description = "How the azurerm provider registers Azure resource providers. none avoids slow, subscription-wide registration; register missing providers by hand."
  default     = "none"
}

variable "models_catalog_path" {
  type        = string
  description = "Path to the model catalog (components/country_packs/models.yaml). Deployments are built from it."
  default     = "../../../components/country_packs/models.yaml"
}

variable "model_capacity" {
  type        = map(number)
  description = "Deployment capacity (thousands of tokens per minute) by tier."
  default = {
    small     = 10
    large     = 10
    embedding = 10
  }
}

variable "search_sku" {
  type        = string
  description = "AI Search SKU: free, basic or standard."
  default     = "free"
}

variable "enable_container_apps" {
  type        = bool
  description = "Deploy agent_app, claims_api and web_ui to Container Apps. Off until the images are built and pushed."
  default     = false
}

variable "container_images" {
  type = object({
    agent_app  = string
    claims_api = string
    web_ui     = string
  })
  description = "Full image references, built with make build C=<app>. Required when enable_container_apps is true."
  default = {
    agent_app  = ""
    claims_api = ""
    web_ui     = ""
  }
}

variable "registry_server" {
  type        = string
  description = "Private registry host for the images (for example an ACR login server). Null means public images."
  default     = null
}

variable "allowed_ip_ranges" {
  type        = list(string)
  description = "CIDR ranges allowed to reach the public apps, normally Cloudflare's published IPv4 ranges (see terraform.tfvars.example)."
  default     = []
}

variable "acknowledge_unrestricted_ingress" {
  type        = bool
  description = "Publish the apps with no IP allow list. There is no user sign-in, so this lets anyone chat, spend tokens and approve claims."
  default     = false
}

variable "enable_apim" {
  type        = bool
  description = "Create the API Management gateway. Developer tier costs about as much as the whole monthly budget, so apply it only while testing and destroy it after (ADR-001)."
  default     = false
}

variable "apim_sku" {
  type        = string
  description = "API Management SKU. Must support llm-token-limit."
  default     = "Developer_1"
}

variable "apim_publisher_email" {
  type        = string
  description = "Publisher email for API Management. Required when enable_apim is true."
  default     = null

  validation {
    condition     = var.apim_publisher_email == null || can(regex("^[^@\\s]+@[^@\\s]+$", var.apim_publisher_email))
    error_message = "apim_publisher_email must look like an email address."
  }
}

variable "apim_country_limits" {
  type = map(object({
    tokens_per_minute  = number
    token_quota        = number
    token_quota_period = optional(string, "Monthly")
  }))
  description = "Token limit per country subscription."
  default = {
    ph = { tokens_per_minute = 20000, token_quota = 2000000 }
    sg = { tokens_per_minute = 20000, token_quota = 2000000 }
    id = { tokens_per_minute = 20000, token_quota = 2000000 }
    th = { tokens_per_minute = 20000, token_quota = 2000000 }
    jp = { tokens_per_minute = 20000, token_quota = 2000000 }
  }
}

variable "apim_extra_allowed_addresses" {
  type        = list(string)
  description = "Single IPs allowed through the gateway's Cloudflare filter, for callers that do not come through Cloudflare."
  default     = []
}

variable "apim_claims_api_url" {
  type        = string
  description = "Base URL the gateway uses for the claims API. Null leaves the claims API out of the gateway."
  default     = null
}

variable "enable_workbook" {
  type        = bool
  description = "Deploy the dashboard workbook into Application Insights."
  default     = true
}

variable "enable_budget_function" {
  type        = bool
  description = "Create the budget controller function and its alert. Needs a code package to do anything (make package-budget)."
  default     = false
}

variable "budget_function_package" {
  type        = string
  description = "Path to the zip from make package-budget. Null leaves code deployment to a human."
  default     = null
}
