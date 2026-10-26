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
  description = "Resource group for the endpoints."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "subnet_id" {
  type        = string
  description = "Subnet that holds the private endpoints."
}

variable "endpoints" {
  type = map(object({
    resource_id      = string
    subresource_name = string
    dns_zone_ids     = list(string)
  }))
  description = "Private endpoints to create, keyed by a short name (for example ai, search, blob, vault)."

  validation {
    condition     = alltrue([for e in values(var.endpoints) : length(e.dns_zone_ids) > 0])
    error_message = "Every endpoint needs at least one private DNS zone so its name resolves privately."
  }
}
