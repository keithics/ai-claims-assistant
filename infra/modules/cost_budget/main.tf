locals {
  start_date = coalesce(var.start_date, formatdate("YYYY-MM-01'T'00:00:00'Z'", timestamp()))

  notifications = {
    actual_50    = { threshold = 50, threshold_type = "Actual" }
    actual_80    = { threshold = 80, threshold_type = "Actual" }
    actual_100   = { threshold = 100, threshold_type = "Actual" }
    forecast_100 = { threshold = 100, threshold_type = "Forecasted" }
  }

  contact_groups = var.action_group_id == null ? [] : [var.action_group_id]

  subscription_budgets = var.enable_subscription_budget ? { main = var.subscription_id } : {}
}

resource "azurerm_consumption_budget_resource_group" "this" {
  name              = "budget-${var.name_prefix}"
  resource_group_id = var.resource_group_id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = local.start_date
  }

  dynamic "notification" {
    for_each = local.notifications

    content {
      operator       = "GreaterThan"
      threshold      = notification.value.threshold
      threshold_type = notification.value.threshold_type
      contact_emails = var.budget_alert_emails
      contact_groups = local.contact_groups
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_consumption_budget_subscription" "this" {
  for_each = local.subscription_budgets

  name            = "budget-sub-${var.name_prefix}"
  subscription_id = each.value
  amount          = var.monthly_budget_usd
  time_grain      = "Monthly"

  time_period {
    start_date = local.start_date
  }

  dynamic "notification" {
    for_each = local.notifications

    content {
      operator       = "GreaterThan"
      threshold      = notification.value.threshold
      threshold_type = notification.value.threshold_type
      contact_emails = var.budget_alert_emails
      contact_groups = local.contact_groups
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}
