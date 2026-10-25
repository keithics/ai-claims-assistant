# Terraform state bootstrap

Creates the resource group and storage account that hold remote state for every env. This is the only stack that uses local state, because it creates the place the other states live.

## What it creates

- Resource group `rg-<project_name>-tfstate`
- Storage account (Standard LRS, TLS 1.2, no public blob access, shared key disabled, blob versioning and soft delete on)
- Private container `tfstate`
- `Storage Blob Data Contributor` for whoever runs it, so Azure AD auth works for the backend

## One-time run

```sh
azph login
cp terraform.tfvars.example terraform.tfvars   # fill in real values; gitignored
terraform init
terraform plan
terraform apply   # needs human approval, see AGENTS.md
terraform output -raw backend_config
```

Keep the local `terraform.tfstate` file safe (it is gitignored). If you lose it, import the resources or recreate them; env state is not lost, only this stack's record of the storage account.

## Pointing an env at it

For now the envs use local state too, so skip this section until remote state is wanted. The storage here is ready for when they switch.

Each env uses the same account and container with its own key. In `infra/envs/<env>/backend.hcl`:

```hcl
resource_group_name  = "<from output>"
storage_account_name = "<from output>"
container_name       = "tfstate"
key                  = "<env>.tfstate"
use_azuread_auth     = true
```

Then `terraform init -backend-config=backend.hcl`. The env's `versions.tf` declares an empty `backend "azurerm" {}` block. State storage costs a few cents a month.
