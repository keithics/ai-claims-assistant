mock_provider "azurerm" {}

variables {
  name                = "srch-claims-assistant-dev-abc123"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
}

run "free_and_keyless_by_default" {
  command = plan

  assert {
    condition     = azurerm_search_service.this.sku == "free" && azurerm_search_service.this.local_authentication_enabled == false
    error_message = "default must be the free SKU with local auth off"
  }

  assert {
    condition     = azurerm_search_service.this.replica_count == null && azurerm_search_service.this.partition_count == null
    error_message = "free SKU must not set replicas or partitions"
  }
}

run "basic_sets_replicas_and_partitions" {
  command = plan

  variables {
    sku = "basic"
  }

  assert {
    condition     = azurerm_search_service.this.replica_count == 1 && azurerm_search_service.this.partition_count == 1
    error_message = "basic should set one replica and one partition"
  }
}

run "role_assignments_are_created" {
  command = plan

  variables {
    role_assignments = {
      app    = { principal_id = "11111111-1111-1111-1111-111111111111", role = "Search Index Data Reader" }
      ingest = { principal_id = "22222222-2222-2222-2222-222222222222", role = "Search Index Data Contributor" }
    }
  }

  assert {
    condition     = length(azurerm_role_assignment.this) == 2
    error_message = "expected two role assignments"
  }
}

run "rejects_expensive_sku" {
  command = plan

  variables {
    sku = "storage_optimized_l2"
  }

  expect_failures = [var.sku]
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
