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
  description = "Resource group for the function."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "storage_account_id" {
  type        = string
  description = "Storage account that holds the budget state and the function package. The function identity gets Storage Blob Data Owner on it."
}

variable "storage_account_name" {
  type        = string
  description = "Name of that storage account."
}

variable "storage_blob_endpoint" {
  type        = string
  description = "Primary blob endpoint of that storage account, for example https://name.blob.core.windows.net/."

  validation {
    condition     = can(regex("^https://", var.storage_blob_endpoint))
    error_message = "storage_blob_endpoint must start with https://."
  }
}

variable "state_container_name" {
  type        = string
  description = "Existing container that holds state.json. The module reads and writes it; it does not create it."
  default     = "budget-state"
}

variable "log_analytics_workspace_id" {
  type        = string
  description = "Resource ID of the Log Analytics workspace with the span data. The function identity gets Log Analytics Reader on it, and the alert rule is scoped to it."
}

variable "log_analytics_workspace_guid" {
  type        = string
  description = "Customer ID (GUID) of that workspace, used by the query client."
}

variable "application_insights_id" {
  type        = string
  description = "Application Insights the function sends its own telemetry to (Monitoring Metrics Publisher)."
}

variable "application_insights_connection_string" {
  type        = string
  description = "Application Insights connection string."
  sensitive   = true
}

variable "action_group_id" {
  type        = string
  description = "Action group notified when a country's budget state changes."
}

variable "package_path" {
  type        = string
  description = "Zip built by `make package-budget`. Null leaves code deployment to a human."
  default     = null
}

variable "python_version" {
  type        = string
  description = "Python runtime of the function."
  default     = "3.12"

  validation {
    condition     = contains(["3.10", "3.11", "3.12"], var.python_version)
    error_message = "python_version must be 3.10, 3.11 or 3.12."
  }
}

variable "maximum_instance_count" {
  type        = number
  description = "Upper bound on instances. A 15 minute timer never needs more than one."
  default     = 40

  validation {
    condition     = var.maximum_instance_count >= 40 && var.maximum_instance_count <= 1000
    error_message = "Flex Consumption allows 40 to 1000 maximum instances."
  }
}

variable "alert_severity" {
  type        = number
  description = "Severity (0 critical to 4 verbose) of the budget-state alert."
  default     = 2

  validation {
    condition     = var.alert_severity >= 0 && var.alert_severity <= 4
    error_message = "alert_severity must be between 0 and 4."
  }
}
