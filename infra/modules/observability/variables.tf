variable "name_prefix" {
  type        = string
  description = "Name prefix from the naming module."
}

variable "location" {
  type        = string
  description = "Azure region for the workspace and Application Insights."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group that holds the observability resources."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "action_group_emails" {
  type        = list(string)
  description = "Email addresses the action group notifies. Set in the env's terraform.tfvars."

  validation {
    condition     = length(var.action_group_emails) > 0 && alltrue([for e in var.action_group_emails : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", e))])
    error_message = "action_group_emails must hold at least one valid email address."
  }
}

variable "retention_days" {
  type        = number
  description = "Log Analytics retention in days. 30 is the lowest Azure allows."
  default     = 30

  validation {
    condition     = var.retention_days >= 30 && var.retention_days <= 730
    error_message = "retention_days must be between 30 and 730."
  }
}

variable "daily_cap_gb" {
  type        = number
  description = "Daily ingestion cap in GB, applied to the workspace and Application Insights. Protects against runaway logging cost."
  default     = 1

  validation {
    condition     = var.daily_cap_gb > 0
    error_message = "daily_cap_gb must be greater than 0."
  }
}

variable "local_authentication_enabled" {
  type        = bool
  description = "Allow instrumentation-key auth on Application Insights. Off by default: apps authenticate with Entra ID and need the Monitoring Metrics Publisher role."
  default     = false
}

variable "enable_workbook" {
  type        = bool
  description = "Deploy the dashboard workbook (four tabs: executive, cost, engineering, quality)."
  default     = false
}

variable "workbook_template_path" {
  type        = string
  description = "Path to the workbook template (components/telemetry/workbook/dashboard.workbook.json), passed in by the env. It may use $${workspace_id}, which is replaced with the Log Analytics workspace ID. Required when enable_workbook is true."
  default     = null

  validation {
    condition     = !var.enable_workbook || var.workbook_template_path != null
    error_message = "workbook_template_path is required when enable_workbook is true."
  }
}
