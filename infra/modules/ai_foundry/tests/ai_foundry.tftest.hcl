mock_provider "azurerm" {}

variables {
  name                = "ais-claims-assistant-dev-abc123"
  project_name        = "proj-claims-assistant-dev"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant" }
  deployments = {
    small-a = { model_name = "gpt-4.1-mini", model_version = "2025-04-14" }
    large   = { model_name = "gpt-4.1", model_version = "2025-04-14", capacity = 5 }
  }
}

run "keyless_account_with_project_and_deployments" {
  command = plan

  assert {
    condition     = azurerm_cognitive_account.this.local_auth_enabled == false && azurerm_cognitive_account.this.kind == "AIServices"
    error_message = "local auth must be off on an AIServices account"
  }

  assert {
    condition     = azurerm_cognitive_account.this.custom_subdomain_name == "ais-claims-assistant-dev-abc123"
    error_message = "subdomain should default to the account name"
  }

  assert {
    condition     = azurerm_cognitive_account.this.project_management_enabled == true
    error_message = "project management must be on for Foundry projects"
  }

  assert {
    condition     = length(azurerm_cognitive_deployment.this) == 2 && azurerm_cognitive_deployment.this["large"].sku[0].capacity == 5 && azurerm_cognitive_deployment.this["small-a"].sku[0].capacity == 10
    error_message = "deployments or capacities wrong"
  }

  assert {
    condition     = alltrue([for d in azurerm_cognitive_deployment.this : d.sku[0].name == "GlobalStandard"])
    error_message = "deployments should default to GlobalStandard pay-as-you-go"
  }
}

run "rejects_provisioned_throughput" {
  command = plan

  variables {
    deployments = {
      big = { model_name = "gpt-4.1", model_version = "2025-04-14", sku_name = "ProvisionedManaged" }
    }
  }

  expect_failures = [var.deployments]
}

run "rejects_large_capacity" {
  command = plan

  variables {
    deployments = {
      big = { model_name = "gpt-4.1", model_version = "2025-04-14", capacity = 500 }
    }
  }

  expect_failures = [var.deployments]
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
