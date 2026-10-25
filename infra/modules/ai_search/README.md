# ai_search

Azure AI Search service. The index itself is created by the `rag` ingestion (F-018), not Terraform.

- `sku` defaults to `free` (one per subscription, 3 indexes, 50 MB). Use `basic` if that is too small or the subscription already has a free service. `standard` and above are not allowed here to protect spend.
- Key auth is off by default (`local_authentication_enabled = false`); callers use Entra ID roles: `Search Index Data Reader` for the app, `Search Index Data Contributor` for ingestion.
- **Unverified:** whether the free SKU accepts key auth being disabled. If the first apply rejects it, set the SKU to `basic` or enable local auth for dev, and record the decision.
- The free SKU ignores `replica_count`, `partition_count`, private endpoints and semantic ranking.
- Takes `name` from the naming module.

## Inputs

`name`, `location`, `resource_group_name`, `tags` (required); `sku`, `replica_count`, `partition_count`, `local_authentication_enabled`, `public_network_access_enabled`, `role_assignments`.

## Outputs

`id`, `name`, `endpoint`.

## Example

```hcl
module "ai_search" {
  source              = "../../modules/ai_search"
  name                = module.naming.names.search_service
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  role_assignments = {
    ingest = { principal_id = data.azurerm_client_config.current.object_id, role = "Search Index Data Contributor" }
  }
}
```

## Tests

`terraform init && terraform test` (mocked provider).
