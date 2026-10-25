# Environments

One folder per env (`dev`, `staging`). Each composes the naming module, the env resource group, the cost budget and observability. Later features add their modules here.

## State

Local state for now: `terraform.tfstate` sits in the env folder and is gitignored. The remote state storage from `infra/bootstrap` is ready for when you switch (add a `backend "azurerm" {}` block and `terraform init -migrate-state`).

## Run

```sh
cp terraform.tfvars.example terraform.tfvars   # fill in real values; gitignored
export AZURE_CONFIG_DIR=$HOME/.azure-azph      # if you log in with azph
make plan ENV=dev
make apply ENV=dev                              # human approval required
```

`resource_provider_registrations` defaults to `none` so the plan does not hang trying to register providers on a sandbox subscription. If an apply says a resource provider is not registered, register it yourself.

## Order

The budget needs the observability action group, so the order is resource group, observability (no billable use until data flows), then the budget. Nothing else is created before the budget.
