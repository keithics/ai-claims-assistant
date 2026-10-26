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
  description = "Resource group for the network."
}

variable "tags" {
  type        = map(string)
  description = "Tags from the naming module."
}

variable "address_space" {
  type        = string
  description = "CIDR of the virtual network."
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.address_space))
    error_message = "address_space must be an IPv4 CIDR range."
  }
}

variable "subnets" {
  type        = map(string)
  description = "Subnet name to CIDR. Must sit inside address_space."
  default = {
    private-endpoints = "10.40.0.0/24"
    apps              = "10.40.4.0/23"
  }

  validation {
    condition     = contains(keys(var.subnets), "private-endpoints")
    error_message = "A private-endpoints subnet is required."
  }

  validation {
    condition     = alltrue([for c in values(var.subnets) : can(cidrnetmask(c))])
    error_message = "Every subnet must be an IPv4 CIDR range."
  }
}

variable "private_dns_zones" {
  type        = set(string)
  description = "Private DNS zones linked to the network, one per private-link service used."
  default = [
    "privatelink.cognitiveservices.azure.com",
    "privatelink.openai.azure.com",
    "privatelink.services.ai.azure.com",
    "privatelink.search.windows.net",
    "privatelink.blob.core.windows.net",
    "privatelink.vaultcore.azure.net",
  ]
}
