# cost_budget

Monthly Azure consumption budget on the env's resource group, applied first in every env (before anything billable exists).

**A budget only alerts. It does not stop spending.** To actually limit cost, run `make destroy ENV=<env>` and rely on the per-country `budget_controller`.

## What it creates

- `azurerm_consumption_budget_resource_group`, monthly, default 50 USD, starting on the first day of the month it is created. `time_period` is ignored after creation so the start date does not drift.
- Notifications on **actual** spend at 50%, 80% and 100%, and on **forecasted** spend at 100%.
- Recipients are `budget_alert_emails` plus the optional `action_group_id`.
- Optionally (`enable_subscription_budget = true`) the same budget at subscription scope.

This module takes `resource_group_id` instead of `resource_group_name`, `location` and `tags`, because budgets are scoped by ID and are not tagged or located.

## Inputs

| Name | Description | Default |
|------|-------------|---------|
| `name_prefix` | From the naming module | required |
| `resource_group_id` | Scope of the budget | required |
| `budget_alert_emails` | Alert recipients; set in the env's gitignored `terraform.tfvars` | required |
| `monthly_budget_usd` | Must be greater than 0 | `50` |
| `action_group_id` | Observability action group to notify too | `null` |
| `start_date` | `YYYY-MM-01T00:00:00Z`; null means this month | `null` |
| `enable_subscription_budget` | Also budget the whole subscription | `false` |
| `subscription_id` | `/subscriptions/<guid>`, needed when the above is true | `null` |

## Outputs

`budget_id` and `budget_amount_usd`. The emails are not output.

## Example

```hcl
module "cost_budget" {
  source              = "../../modules/cost_budget"
  name_prefix         = module.naming.name_prefix
  resource_group_id   = azurerm_resource_group.main.id
  budget_alert_emails = var.budget_alert_emails
  action_group_id     = module.observability.action_group_id
}
```

## Tests

`terraform init && terraform test` from this folder (uses a mocked provider, no Azure access needed).
