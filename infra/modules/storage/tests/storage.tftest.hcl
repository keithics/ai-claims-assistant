mock_provider "azurerm" {}

variables {
  name                = "stclaimsdevabc123"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
}

run "locked_down_with_default_containers" {
  command = plan

  assert {
    condition     = azurerm_storage_account.this.shared_access_key_enabled == false && azurerm_storage_account.this.allow_nested_items_to_be_public == false
    error_message = "shared key must be off and public blobs disallowed"
  }

  assert {
    condition     = length(azurerm_storage_container.this) == 3 && contains(keys(azurerm_storage_container.this), "policies") && contains(keys(azurerm_storage_container.this), "eval-results") && contains(keys(azurerm_storage_container.this), "budget-state")
    error_message = "expected policies, eval-results and budget-state containers"
  }

  assert {
    condition     = alltrue([for c in azurerm_storage_container.this : c.container_access_type == "private"])
    error_message = "containers must be private"
  }
}

run "role_assignments_are_created" {
  command = plan

  variables {
    role_assignments = {
      ingest = { principal_id = "11111111-1111-1111-1111-111111111111", role = "Storage Blob Data Contributor" }
    }
  }

  assert {
    condition     = length(azurerm_role_assignment.this) == 1
    error_message = "expected one role assignment"
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
