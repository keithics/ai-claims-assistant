variable "name" {
  type        = string
  description = "Key Vault name from the naming module (3-24 characters, globally unique)."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the vault."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "tenant_id" {
  type        = string
  description = "Entra tenant ID that authenticates requests to the vault."
}

variable "sku_name" {
  type        = string
  description = "Key Vault SKU."
  default     = "standard"

  validation {
    condition     = contains(["standard", "premium"], var.sku_name)
    error_message = "sku_name must be standard or premium."
  }
}

variable "purge_protection_enabled" {
  type        = bool
  description = "Purge protection. Off in dev so the vault can be destroyed and recreated."
  default     = false
}

variable "soft_delete_retention_days" {
  type        = number
  description = "Days soft-deleted items are kept."
  default     = 7

  validation {
    condition     = var.soft_delete_retention_days >= 7 && var.soft_delete_retention_days <= 90
    error_message = "soft_delete_retention_days must be between 7 and 90."
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
  description = "Role assignments on the vault, keyed by a stable name. Least privilege: use Secrets User for apps."
  default     = {}

  validation {
    condition = alltrue([
      for a in values(var.role_assignments) :
      contains(["Key Vault Secrets User", "Key Vault Secrets Officer", "Key Vault Administrator"], a.role)
    ])
    error_message = "role must be Key Vault Secrets User, Key Vault Secrets Officer or Key Vault Administrator."
  }
}
