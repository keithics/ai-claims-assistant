# keyvault

Key Vault with RBAC authorisation (no access policies). Anything secret lives here; apps read it with their managed identity.

Takes `name` (from the naming module, globally unique) instead of `name_prefix`, because Key Vault names need a unique suffix and the naming module already builds it.

- `purge_protection_enabled` defaults to `false` so `make destroy` works in dev. Turn it on for anything long-lived.
- `public_network_access_enabled` defaults to `true`; the private networking feature (F-055) turns it off.
- `role_assignments`: map of `{ principal_id, role }`. Allowed roles: Key Vault Secrets User (apps), Secrets Officer, Administrator.

## Inputs

`name`, `location`, `resource_group_name`, `tags`, `tenant_id` (required); `sku_name` (`standard`), `purge_protection_enabled`, `soft_delete_retention_days` (7), `public_network_access_enabled`, `role_assignments`.

## Outputs

`id`, `name`, `vault_uri`.

## Example

```hcl
module "keyvault" {
  source              = "../../modules/keyvault"
  name                = module.naming.names.key_vault
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = module.naming.tags
  tenant_id           = data.azurerm_client_config.current.tenant_id
  role_assignments = {
    deployer = { principal_id = data.azurerm_client_config.current.object_id, role = "Key Vault Secrets Officer" }
  }
}
```

## Tests

`terraform init && terraform test` (mocked provider).
