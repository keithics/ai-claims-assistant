variable "subscription_id" {
  type        = string
  description = "Azure subscription that will hold the Terraform state."
}

variable "project_name" {
  type        = string
  description = "Project name used in resource names and the project tag."
  default     = "claims-assistant"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,19}$", var.project_name))
    error_message = "project_name must be 2-20 characters: lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "location" {
  type        = string
  description = "Azure region for the state resources."
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

variable "state_container_name" {
  type        = string
  description = "Blob container that holds the state files, one blob per env."
  default     = "tfstate"
}

variable "blob_retention_days" {
  type        = number
  description = "Days deleted state blobs and old versions stay recoverable."
  default     = 14

  validation {
    condition     = var.blob_retention_days >= 1 && var.blob_retention_days <= 365
    error_message = "blob_retention_days must be between 1 and 365."
  }
}
