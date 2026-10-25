# storage

Storage account for the policy documents (`policies` container) and evaluation results (`eval-results`). Shared-key access is disabled, so everything uses Entra ID, and blobs can never be public.

Takes `name` (from the naming module, globally unique) instead of `name_prefix`.

## Inputs

`name`, `location`, `resource_group_name`, `tags` (required); `containers` (`policies`, `eval-results`), `replication_type` (`LRS`), `blob_retention_days` (7), `public_network_access_enabled`, `role_assignments` (Storage Blob Data Reader or Contributor only).

## Outputs

`id`, `name`, `blob_endpoint`, `container_names`.

## Example

```hcl
module "storage" {
  source              = "../../modules/storage"
  name                = module.naming.names.storage_account
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
}
```

## Tests

`terraform init && terraform test` (mocked provider).
