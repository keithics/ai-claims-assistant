variable "project_name" {
  type        = string
  description = "Project name, used in every resource name and the project tag."
  default     = "claims-assistant"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,23}[a-z0-9]$", var.project_name))
    error_message = "project_name must be 3-25 characters: lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen."
  }
}

variable "env" {
  type        = string
  description = "Environment name."

  validation {
    condition     = contains(["dev", "staging"], var.env)
    error_message = "env must be one of: dev, staging."
  }
}

variable "owner" {
  type        = string
  description = "Owner tag value."

  validation {
    condition     = trimspace(var.owner) != ""
    error_message = "owner must not be empty."
  }
}

variable "cost_center" {
  type        = string
  description = "Cost center tag value."

  validation {
    condition     = trimspace(var.cost_center) != ""
    error_message = "cost_center must not be empty."
  }
}

variable "country" {
  type        = string
  description = "Country code for country-specific resources. Null for shared resources."
  default     = null

  validation {
    condition     = var.country == null || contains(["ph", "sg", "id", "th", "jp"], coalesce(var.country, "none"))
    error_message = "country must be null or one of: ph, sg, id, th, jp."
  }
}

variable "unique_suffix" {
  type        = string
  description = "Short lowercase suffix added to globally unique names (storage, Key Vault, Search). Pass a random_string result from the env."
  default     = ""

  validation {
    condition     = can(regex("^[a-z0-9]{0,8}$", var.unique_suffix))
    error_message = "unique_suffix must be 0-8 lowercase letters or digits."
  }
}
