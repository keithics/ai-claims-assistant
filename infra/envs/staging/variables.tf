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
