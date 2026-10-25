# naming

Creates no resources. Turns `project_name`, `env`, `owner`, `cost_center` and an optional `country` into a name prefix, per-resource-type names and the required tag map. Every env builds its names and tags here.

This is the one module that does not take `name_prefix`, `location`, `resource_group_name` and `tags`, because it produces them.

## Inputs

| Name | Description | Default |
|------|-------------|---------|
| `project_name` | Project name, lowercase, 3-25 characters | `claims-assistant` |
| `env` | `dev` or `staging` | required |
| `owner` | Owner tag | required |
| `cost_center` | Cost center tag | required |
| `country` | `ph`, `sg`, `id`, `th`, `jp` or null | `null` |
| `unique_suffix` | 0-8 lowercase alphanumerics for globally unique names | `""` |

## Outputs

- `name_prefix`: `<project>-<env>[-<country>]`
- `names`: map of resource type to name (`resource_group`, `storage_account`, `key_vault`, `search_service`, `log_analytics`, and more)
- `tags`: `project`, `env`, `owner`, `cost_center`, plus `country` when set

Storage accounts (3-24, lowercase alphanumeric), Key Vaults (3-24, single hyphens) and Search services (2-60) are truncated from the prefix side, so `unique_suffix` always survives. Pass a `random_string` result as the suffix to keep those names globally unique.

## Example

```hcl
module "naming" {
  source        = "../../modules/naming"
  env           = "dev"
  owner         = "team-a"
  cost_center   = "cc-1"
  unique_suffix = random_string.suffix.result
}

resource "azurerm_resource_group" "main" {
  name     = module.naming.names.resource_group
  location = var.location
  tags     = module.naming.tags
}
```

## Tests

`terraform init && terraform test` from this folder.
