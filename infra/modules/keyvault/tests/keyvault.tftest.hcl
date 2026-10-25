mock_provider "azurerm" {}

variables {
  name                = "kv-claims-dev-abc123"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
  tenant_id           = "00000000-0000-0000-0000-000000000000"
}

run "rbac_on_and_purge_protection_off_by_default" {
  command = plan

  assert {
    condition     = azurerm_key_vault.this.rbac_authorization_enabled == true && azurerm_key_vault.this.purge_protection_enabled == false
    error_message = "RBAC must be on and purge protection off by default"
  }

  assert {
    condition     = length(azurerm_role_assignment.this) == 0
    error_message = "no role assignments by default"
  }
}

run "role_assignments_are_created" {
  command = plan

  variables {
    role_assignments = {
      app      = { principal_id = "11111111-1111-1111-1111-111111111111", role = "Key Vault Secrets User" }
      deployer = { principal_id = "22222222-2222-2222-2222-222222222222", role = "Key Vault Secrets Officer" }
    }
  }

  assert {
    condition     = length(azurerm_role_assignment.this) == 2
    error_message = "expected two role assignments"
  }
}

run "rejects_broad_role" {
  command = plan

  variables {
    role_assignments = {
      app = { principal_id = "11111111-1111-1111-1111-111111111111", role = "Owner" }
    }
  }

  expect_failures = [var.role_assignments]
}

run "rejects_bad_sku" {
  command = plan

  variables {
    sku_name = "basic"
  }

  expect_failures = [var.sku_name]
}
