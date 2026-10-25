variable "name" {
  type        = string
  description = "Storage account name from the naming module (3-24 lowercase alphanumerics, globally unique)."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the account."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "containers" {
  type        = set(string)
  description = "Private blob containers to create."
  default     = ["policies", "eval-results", "budget-state"]
}

variable "replication_type" {
  type        = string
  description = "Account replication type."
  default     = "LRS"

  validation {
    condition     = contains(["LRS", "ZRS", "GRS", "GZRS"], var.replication_type)
    error_message = "replication_type must be LRS, ZRS, GRS or GZRS."
  }
}

variable "blob_retention_days" {
  type        = number
  description = "Soft-delete retention for blobs and containers."
  default     = 7

  validation {
    condition     = var.blob_retention_days >= 1 && var.blob_retention_days <= 365
    error_message = "blob_retention_days must be between 1 and 365."
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
      contains(["Storage Blob Data Reader", "Storage Blob Data Contributor"], a.role)
    ])
    error_message = "role must be Storage Blob Data Reader or Storage Blob Data Contributor."
  }
}
