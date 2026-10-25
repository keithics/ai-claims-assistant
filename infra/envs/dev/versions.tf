terraform {
  required_version = ">= 1.6"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9.0"
    }
  }
}

provider "azurerm" {
  subscription_id                 = var.subscription_id
  resource_provider_registrations = var.resource_provider_registrations
  storage_use_azuread             = true
  features {}
}

provider "azapi" {
  subscription_id = var.subscription_id
}
