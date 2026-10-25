mock_provider "azurerm" {}

variables {
  name_prefix         = "claims-assistant-dev"
  location            = "southeastasia"
  resource_group_name = "rg-test"
  tags                = { project = "claims-assistant", env = "dev" }
  action_group_emails = ["alerts@example.com", "ops@example.com"]
}

run "short_retention_and_daily_cap_by_default" {
  command = plan

  assert {
    condition     = azurerm_log_analytics_workspace.this.retention_in_days == 30 && azurerm_log_analytics_workspace.this.daily_quota_gb == 1
    error_message = "workspace should default to 30 days and a 1 GB daily cap"
  }

  assert {
    condition     = azurerm_application_insights.this.daily_data_cap_in_gb == 1 && azurerm_application_insights.this.local_authentication_enabled == false
    error_message = "App Insights should have the daily cap and local auth off"
  }
}

run "action_group_has_one_receiver_per_email" {
  command = plan

  assert {
    condition     = length(azurerm_monitor_action_group.this.email_receiver) == 2
    error_message = "expected two email receivers"
  }

  assert {
    condition     = length(azurerm_monitor_action_group.this.short_name) <= 12
    error_message = "action group short name must be at most 12 characters"
  }
}

run "workbook_is_off_by_default" {
  command = plan

  assert {
    condition     = length(azurerm_application_insights_workbook.this) == 0
    error_message = "workbook must not be created by default"
  }
}

run "workbook_needs_a_template_path" {
  command = plan

  variables {
    enable_workbook = true
  }

  expect_failures = [var.workbook_template_path]
}

run "rejects_empty_emails" {
  command = plan

  variables {
    action_group_emails = []
  }

  expect_failures = [var.action_group_emails]
}

run "rejects_retention_below_30" {
  command = plan

  variables {
    retention_days = 7
  }

  expect_failures = [var.retention_days]
}
