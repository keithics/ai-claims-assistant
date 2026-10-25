# ai_foundry

AI Services account (`AIServices`), a Foundry project and model deployments. Uses only `azurerm` (4.81 has `azurerm_cognitive_account_project`), so no `azapi`.

- Local (key) auth is disabled; callers use Entra ID with `Cognitive Services OpenAI User` (grant it to the gateway identity, not the apps: apps call the gateway only).
- Deployments are pay-as-you-go (`Standard`, `GlobalStandard`, `DataZoneStandard`) with small capacity (1-100, thousands of tokens per minute). Provisioned throughput is rejected.
- One module call is one region. A market that needs its own region (for example Japan East) gets its own call.
- `GlobalStandard` can process requests outside the account's region. Decide per country in ADR-003.
- Takes `name` and `project_name` from the naming module (the name doubles as the globally unique subdomain).
- The project is created after the deployments, because Azure rejects two operations on one account at once (409 conflict). Several deployments created in parallel can still conflict; if so, re-run the apply.
- Each deployment needs quota in the subscription (tokens per minute by model and SKU). Check with `az cognitiveservices usage list -l <region>`; an `InsufficientQuota` error means that model has none, and re-running will not help.

## Inputs

`name`, `project_name`, `location`, `resource_group_name`, `tags`, `deployments` (required); `custom_subdomain_name`, `public_network_access_enabled`, `role_assignments`.

## Outputs

`account_id`, `project_id`, `endpoint`, `openai_endpoint`, `deployment_names`, `principal_id`. No keys.

## Example

```hcl
module "ai_foundry" {
  source              = "../../modules/ai_foundry"
  name                = module.naming.names.ai_services
  project_name        = module.naming.names.foundry_project
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  deployments = {
    small-a = { model_name = "gpt-4.1-mini", model_version = "2025-04-14" }
  }
}
```

## Tests

`terraform init && terraform test` (mocked provider).
