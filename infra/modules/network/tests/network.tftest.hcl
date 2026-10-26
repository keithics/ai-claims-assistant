mock_provider "azurerm" {}

variables {
  name_prefix         = "claims-assistant-dev"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
}

run "creates_a_vnet_with_subnets_and_linked_private_dns_zones" {
  command = plan

  assert {
    condition     = toset(keys(azurerm_subnet.this)) == toset(["private-endpoints", "apps"])
    error_message = "Expected the private-endpoints and apps subnets."
  }

  assert {
    condition     = length(azurerm_private_dns_zone.this) == 6 && length(azurerm_private_dns_zone_virtual_network_link.this) == 6
    error_message = "Every zone must be linked to the network."
  }

  assert {
    condition     = contains(keys(azurerm_private_dns_zone.this), "privatelink.openai.azure.com") && contains(keys(azurerm_private_dns_zone.this), "privatelink.vaultcore.azure.net")
    error_message = "Zones for AI Services, Search, Blob and Key Vault are needed."
  }
}

run "needs_a_private_endpoints_subnet" {
  command = plan

  variables {
    subnets = { apps = "10.40.4.0/23" }
  }

  expect_failures = [var.subnets]
}

run "rejects_a_bad_cidr" {
  command = plan

  variables {
    address_space = "not-a-cidr"
  }

  expect_failures = [var.address_space]
}
