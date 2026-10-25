mock_provider "azurerm" {}

variables {
  name_prefix         = "claims-assistant-dev"
  resource_group_id   = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test"
  budget_alert_emails = ["alerts@example.com"]
}

run "defaults_to_50_usd_with_four_notifications" {
  command = plan

  assert {
    condition     = azurerm_consumption_budget_resource_group.this.amount == 50 && azurerm_consumption_budget_resource_group.this.time_grain == "Monthly"
    error_message = "default must be a 50 USD monthly budget"
  }

  assert {
    condition     = length(azurerm_consumption_budget_resource_group.this.notification) == 4
    error_message = "expected actual 50/80/100 and forecasted 100"
  }

  assert {
    condition = length([
      for n in azurerm_consumption_budget_resource_group.this.notification : n
      if n.threshold_type == "Forecasted" && n.threshold == 100
      ]) == 1 && length([
      for n in azurerm_consumption_budget_resource_group.this.notification : n
      if n.threshold_type == "Actual" && contains([50, 80, 100], n.threshold)
    ]) == 3
    error_message = "notification thresholds or types are wrong"
  }

  assert {
    condition     = length(azurerm_consumption_budget_subscription.this) == 0
    error_message = "subscription budget must be off by default"
  }
}

run "action_group_is_added_to_every_notification" {
  command = plan

  variables {
    action_group_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-test/providers/microsoft.insights/actionGroups/ag"
  }

  assert {
    condition     = alltrue([for n in azurerm_consumption_budget_resource_group.this.notification : length(n.contact_groups) == 1])
    error_message = "every notification should include the action group"
  }
}

run "subscription_budget_when_enabled" {
  command = plan

  variables {
    enable_subscription_budget = true
    subscription_id            = "/subscriptions/00000000-0000-0000-0000-000000000000"
  }

  assert {
    condition     = length(azurerm_consumption_budget_subscription.this) == 1
    error_message = "expected one subscription budget"
  }
}

run "rejects_zero_amount" {
  command = plan

  variables {
    monthly_budget_usd = 0
  }

  expect_failures = [var.monthly_budget_usd]
}

run "rejects_empty_emails" {
  command = plan

  variables {
    budget_alert_emails = []
  }

  expect_failures = [var.budget_alert_emails]
}

run "rejects_start_date_not_first_of_month" {
  command = plan

  variables {
    start_date = "2026-10-15T00:00:00Z"
  }

  expect_failures = [var.start_date]
}
