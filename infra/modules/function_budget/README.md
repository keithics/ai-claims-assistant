# function_budget

The Azure Function that runs the budget controller (`components/budget_controller`), plus the alert that fires when a country's budget state changes.

- **Plan:** Flex Consumption (`FC1`), pay per execution, with managed-identity access to storage and no keys. A 15-minute timer costs cents a month.
- **Identity:** one user-assigned identity, created first so its roles exist before the function touches storage. Roles: Storage Blob Data Owner on the storage account (package and `state.json`), Log Analytics Reader on the workspace (spend query), Monitoring Metrics Publisher on Application Insights (its own telemetry).
- **State store:** a blob (`budget-state/state.json`) in the env's storage account. See ADR-006.
- **Alert:** a scheduled query rule on the workspace that counts `budget_state_changed` spans in the last 15 minutes and notifies the observability action group. The function emits one span per change and nothing when states are unchanged.

## Inputs

Required: `name_prefix`, `location`, `resource_group_name`, `tags`, `storage_account_id`, `storage_account_name`, `storage_blob_endpoint`, `log_analytics_workspace_id`, `log_analytics_workspace_guid`, `application_insights_id`, `application_insights_connection_string`, `action_group_id`.

Optional: `state_container_name` (default `budget-state`, created by the storage module), `package_path` (zip from `make package-budget`; null leaves code deployment to you), `python_version`, `maximum_instance_count`, `alert_severity`.

## Outputs

`function_name`, `principal_id`, `alert_rule_id`.

## Example

```hcl
module "function_budget" {
  source = "../../modules/function_budget"

  name_prefix                           = module.naming.name_prefix
  location                              = var.location
  resource_group_name                   = azurerm_resource_group.main.name
  tags                                  = module.naming.tags
  storage_account_id                    = module.storage.id
  storage_account_name                  = module.storage.name
  storage_blob_endpoint                 = module.storage.blob_endpoint
  log_analytics_workspace_id            = module.observability.log_analytics_workspace_id
  log_analytics_workspace_guid          = module.observability.log_analytics_workspace_guid
  application_insights_id               = module.observability.application_insights_id
  application_insights_connection_string = module.observability.application_insights_connection_string
  action_group_id                       = module.observability.action_group_id
}
```
