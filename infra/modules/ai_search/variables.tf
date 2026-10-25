variable "name" {
  type        = string
  description = "Search service name from the naming module (globally unique)."
}

variable "location" {
  type        = string
  description = "Azure region."
}

variable "resource_group_name" {
  type        = string
  description = "Resource group for the service."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "sku" {
  type        = string
  description = "Search SKU. free allows one service per subscription and 3 indexes; use basic when that is too small."
  default     = "free"

  validation {
    condition     = contains(["free", "basic", "standard"], var.sku)
    error_message = "sku must be free, basic or standard."
  }
}

variable "replica_count" {
  type        = number
  description = "Replicas. Ignored on the free SKU."
  default     = 1
}

variable "partition_count" {
  type        = number
  description = "Partitions. Ignored on the free SKU."
  default     = 1
}

variable "local_authentication_enabled" {
  type        = bool
  description = "Allow API-key auth. Off by default: callers use Entra ID roles."
  default     = false
}

variable "public_network_access_enabled" {
  type        = bool
  description = "Allow public network access. Set false when private networking is on (not supported on the free SKU)."
  default     = true
}

variable "role_assignments" {
  type = map(object({
    principal_id = string
    role         = string
  }))
  description = "Role assignments on the service, keyed by a stable name. Readers for the app, contributors for ingestion."
  default     = {}

  validation {
    condition = alltrue([
      for a in values(var.role_assignments) :
      contains(["Search Index Data Reader", "Search Index Data Contributor", "Search Service Contributor"], a.role)
    ])
    error_message = "role must be Search Index Data Reader, Search Index Data Contributor or Search Service Contributor."
  }
}
