variable "name_prefix" {
  type        = string
  description = "Name prefix from the naming module, used in the budget names."
}

variable "resource_group_id" {
  type        = string
  description = "ID of the env's resource group. The budget is scoped to it."
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly budget amount in USD."
  default     = 50

  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "monthly_budget_usd must be greater than 0."
  }
}

variable "budget_alert_emails" {
  type        = list(string)
  description = "Email addresses that receive budget alerts. Set in the env's terraform.tfvars, never in code."

  validation {
    condition     = length(var.budget_alert_emails) > 0 && alltrue([for e in var.budget_alert_emails : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", e))])
    error_message = "budget_alert_emails must hold at least one valid email address."
  }
}

variable "action_group_id" {
  type        = string
  description = "Optional observability action group ID to notify as well."
  default     = null
}

variable "start_date" {
  type        = string
  description = "Budget start date as YYYY-MM-01T00:00:00Z. Null means the first day of the current month at creation time."
  default     = null

  validation {
    condition     = var.start_date == null || can(regex("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$", coalesce(var.start_date, "none")))
    error_message = "start_date must be the first of a month, formatted YYYY-MM-01T00:00:00Z."
  }
}

variable "enable_subscription_budget" {
  type        = bool
  description = "Also create a budget at subscription scope."
  default     = false
}

variable "subscription_id" {
  type        = string
  description = "Subscription resource ID (/subscriptions/<guid>). Required when enable_subscription_budget is true."
  default     = null

  validation {
    condition     = var.subscription_id == null || can(regex("^/subscriptions/[0-9a-fA-F-]{36}$", coalesce(var.subscription_id, "none")))
    error_message = "subscription_id must look like /subscriptions/<guid>."
  }
}
