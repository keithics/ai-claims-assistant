# observability

Log Analytics workspace, workspace-based Application Insights and an action group. Telemetry from every component lands here, and budget and alert rules notify the action group.

## What it creates

- Log Analytics workspace (`PerGB2018`), 30 day retention by default (the lowest Azure allows) and a daily ingestion cap (default 1 GB) so runaway logging cannot run up cost.
- Application Insights linked to that workspace, with the same daily cap. Instrumentation-key auth is off by default; apps authenticate with Entra ID, so each app identity needs the `Monitoring Metrics Publisher` role on the Application Insights resource (granted in the module that creates the app identity).
- Action group with one email receiver per address in `action_group_emails`.
- Dashboard workbook, only when `enable_workbook = true`. It stays off until the template exists (F-042).

## Inputs

| Name | Description | Default |
|------|-------------|---------|
| `name_prefix`, `location`, `resource_group_name`, `tags` | From the env and the naming module | required |
| `action_group_emails` | Alert recipients; set in the env's gitignored `terraform.tfvars` | required |
| `retention_days` | 30 to 730 | `30` |
| `daily_cap_gb` | Daily ingestion cap for the workspace and Application Insights | `1` |
| `local_authentication_enabled` | Allow instrumentation-key auth | `false` |
| `enable_workbook` | Deploy the workbook | `false` |
| `workbook_template_path` | Path to the workbook JSON, passed in by the env | `null` |

## Outputs

`log_analytics_workspace_id`, `application_insights_id`, `application_insights_connection_string` (sensitive), `action_group_id`.

## Example

```hcl
module "observability" {
  source              = "../../modules/observability"
  name_prefix         = module.naming.name_prefix
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  action_group_emails = var.budget_alert_emails
}
```

## Tests

`terraform init && terraform test` from this folder (mocked provider, no Azure access needed).
