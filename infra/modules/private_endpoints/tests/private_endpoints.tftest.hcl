mock_provider "azurerm" {}

variables {
  name_prefix         = "claims-assistant-dev"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
  subnet_id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/v/subnets/s"
  endpoints = {
    ai = {
      resource_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a"
      subresource_name = "account"
      dns_zone_ids     = ["/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Network/privateDnsZones/privatelink.openai.azure.com"]
    }
    vault = {
      resource_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
      subresource_name = "vault"
      dns_zone_ids     = ["/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net"]
    }
  }
}

run "one_endpoint_per_entry_with_automatic_dns" {
  command = plan

  assert {
    condition     = toset(keys(azurerm_private_endpoint.this)) == toset(["ai", "vault"])
    error_message = "One endpoint per entry."
  }

  assert {
    condition     = alltrue([for e in azurerm_private_endpoint.this : !e.private_service_connection[0].is_manual_connection && length(e.private_dns_zone_group[0].private_dns_zone_ids) == 1])
    error_message = "Connections must be automatic and have a DNS zone group."
  }
}

run "refuses_an_endpoint_without_a_dns_zone" {
  command = plan

  variables {
    endpoints = {
      ai = {
        resource_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/a"
        subresource_name = "account"
        dns_zone_ids     = []
      }
    }
  }

  expect_failures = [var.endpoints]
}
