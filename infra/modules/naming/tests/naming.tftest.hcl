variables {
  env         = "dev"
  owner       = "team-a"
  cost_center = "cc-1"
}

run "defaults_shared_resource" {
  command = plan

  assert {
    condition     = output.name_prefix == "claims-assistant-dev"
    error_message = "unexpected prefix"
  }

  assert {
    condition     = output.names.resource_group == "rg-claims-assistant-dev"
    error_message = "unexpected resource group name"
  }

  assert {
    condition     = output.tags == { project = "claims-assistant", env = "dev", owner = "team-a", cost_center = "cc-1" }
    error_message = "tags must be project, env, owner, cost_center and no country"
  }
}

run "country_resource_with_suffix" {
  command = plan

  variables {
    country       = "jp"
    unique_suffix = "a1b2c3"
  }

  assert {
    condition     = output.tags.country == "jp"
    error_message = "country tag missing"
  }

  assert {
    condition     = output.name_prefix == "claims-assistant-dev-jp"
    error_message = "country missing from prefix"
  }

  assert {
    condition     = can(regex("^st[a-z0-9]{1,22}a1b2c3$", output.names.storage_account)) && length(output.names.storage_account) <= 24 && length(output.names.storage_account) >= 3
    error_message = "storage account name must be 3-24 lowercase alphanumeric characters ending in the suffix"
  }

  assert {
    condition     = can(regex("^kv-[a-z0-9-]+$", output.names.key_vault)) && length(output.names.key_vault) <= 24 && !can(regex("--|-$", output.names.key_vault))
    error_message = "Key Vault name must be 3-24 characters, letters, digits and single hyphens, not ending in a hyphen"
  }

  assert {
    condition     = output.names.ai_services == "ais-claims-assistant-dev-jp-a1b2c3" && output.names.foundry_project == "proj-claims-assistant-dev-jp"
    error_message = "AI Services name must carry the unique suffix"
  }

  assert {
    condition     = can(regex("^srch-[a-z0-9-]+$", output.names.search_service)) && length(output.names.search_service) <= 60 && !can(regex("-$", output.names.search_service))
    error_message = "Search service name must be 2-60 characters, lowercase letters, digits and hyphens, not ending in a hyphen"
  }
}

run "longest_inputs_still_fit" {
  command = plan

  variables {
    project_name  = "abcdefghijklmnopqrstuvwxy"
    env           = "staging"
    country       = "th"
    unique_suffix = "zzzzzzzz"
  }

  assert {
    condition     = length(output.names.storage_account) == 24 && endswith(output.names.storage_account, "zzzzzzzz")
    error_message = "storage account must truncate the prefix, not the suffix, and stay at 24"
  }

  assert {
    condition     = length(output.names.key_vault) <= 24 && endswith(output.names.key_vault, "-zzzzzzzz")
    error_message = "Key Vault must truncate the prefix, keep the suffix and stay within 24"
  }

  assert {
    condition     = length(output.names.search_service) <= 60
    error_message = "Search name too long"
  }
}

run "rejects_bad_country" {
  command = plan

  variables {
    country = "vn"
  }

  expect_failures = [var.country]
}

run "rejects_bad_env" {
  command = plan

  variables {
    env = "prod"
  }

  expect_failures = [var.env]
}
