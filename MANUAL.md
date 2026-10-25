# MANUAL.md

Things only a human can do or approve. Agents never run these. Tick them off as you go. "Now" items are needed for what is already built; "Later" items are known from `FEATURES.md` and will be needed when that feature lands.

## Now (F-001 to F-006 are built)

- [ ] **Install uv:** `brew install uv`. Until then, `make` targets need `UV=<path to uv>`.
- [x] **Log in to Azure:** done with `azph login`. `azph` is `az` with `AZURE_CONFIG_DIR=~/.azure-azph`, so Terraform only sees that login if you export `AZURE_CONFIG_DIR=$HOME/.azure-azph` first (the agent sets it per command).
- [ ] **Stop the provider hanging on a sandbox subscription:** export `ARM_RESOURCE_PROVIDER_REGISTRATIONS=none` when running Terraform, or set `resource_provider_registrations = "none"` in the env provider blocks. Without it the azurerm provider tries to register resource providers and the plan hangs. If a later apply fails with a "resource provider not registered" error, register that provider yourself.
- [ ] **Check `infra/bootstrap/terraform.tfvars`:** `owner` and `cost_center` are placeholders (`keithics`, `dev`). The file is gitignored.
- [ ] **Initialise git:** `git init`, then `make setup` to install the pre-commit hooks. Agents only commit when you ask.
- [ ] **Optional tools:** `brew install tflint` (otherwise `make lint` skips it); start Docker if you want to run workflows locally with `act`.
- [ ] **Decide on the bootstrap apply:** the state storage in `infra/bootstrap` is only needed when envs move to remote state. Envs use local state for now, so you can skip it. When you want it: `cd infra/bootstrap && terraform init && terraform plan`, review, then `terraform apply`.

## Later

### Before the first deploy (F-007 to F-009)
- [ ] `infra/envs/dev/terraform.tfvars` exists with your subscription; replace the `CHANGE-ME@example.com` in `budget_alert_emails` with a real address before the first apply, or the alerts go nowhere. Create `infra/envs/staging/terraform.tfvars` the same way when you want staging.
- [ ] Review `make plan ENV=dev`, then run `make apply ENV=dev` yourself or tell the agent explicitly to. The $50 budget is the first thing applied.
- [ ] Repeat for each later infra feature that adds resources (F-013, F-014, F-015, F-029, F-032, F-044, F-055): review the plan, then approve the apply.

### Live checks for Milestone M1 (F-018 to F-020)
- [x] Done 2026-10-25: dev env applied, `make ingest` twice (37 embedded, then 0 embedded and 37 unchanged), and all 5 integration tests pass. The free Search SKU accepted keyless auth.
- Re-run them with the exports below whenever you change ingestion, the retriever or the chat service. Since F-033 every model call goes through the gateway, so it must be applied (`enable_apim = true`) and your public IP must be in `apim_extra_allowed_addresses`:
  ```sh
  export AZURE_CONFIG_DIR=$HOME/.azure-azph
  export RAG_SEARCH_ENDPOINT=$(terraform -chdir=infra/envs/dev output -raw search_endpoint)
  export RAG_GATEWAY_URL=$(terraform -chdir=infra/envs/dev output -raw gateway_url)
  export AGENT_GATEWAY_URL=$RAG_GATEWAY_URL
  for c in ph sg id th jp; do
    export GATEWAY_KEY_$(echo $c | tr a-z A-Z)=$(azph keyvault secret show --vault-name <your key vault> --name apim-models-key-$c --query value -o tsv)
  done
  make ingest
  uv run pytest tests/integration -m integration
  ```
  The Key Vault name is in the `key_vault_uri` output.

### Deploying the apps to Azure (F-029), optional
Running locally needs none of this: `make run FAKE=1` (offline) or `make run` (live Azure, see the exports above).
- [ ] Build the images: `make build C=agent_app`, `make build C=claims_api`, `make build C=web_ui` (needs OrbStack or Docker running).
- [ ] Push them to a registry you control (public, or a private ACR plus `registry_server` and an AcrPull grant for the app identities).
- [ ] Register the `Microsoft.App` resource provider on the subscription (the env sets `resource_provider_registrations = "none"`, so it will not do this for you).
- [ ] In `infra/envs/dev/terraform.tfvars` set `enable_container_apps = true`, `container_images` and `allowed_ip_ranges` (the Cloudflare list is in `terraform.tfvars.example`). Without an allow list the plan refuses to run.
- [ ] Set up Cloudflare Access in front of the hostnames first (see the Cloudflare section), then review `make plan ENV=dev` and approve the apply.
- [ ] Point Cloudflare at the `container_app_urls` outputs.

### Gateway (F-032), optional until the load test

- [ ] Set `apim_publisher_email` in `infra/envs/dev/terraform.tfvars` and `enable_apim = true`. The Developer tier costs about the whole $50 budget and takes 30 to 45 minutes to create, so apply it for a test window and destroy it afterwards.
- [ ] Review `make plan ENV=dev`, then approve the apply. API Management only checks the `llm-*` policy syntax at apply time; if it rejects a policy, send the error back.
- [ ] In the Application Insights resource, turn on "Enable alerting on custom metric dimensions" (Usage and estimated costs, Custom metrics). The provider has no setting for it, and without it the `country`, `app`, `model` and `route_tier` dimensions do not show up.
- [ ] The gateway only accepts Cloudflare's ranges. Either proxy the gateway hostname through Cloudflare, or put the outbound IP of any direct caller (for example the load test machine or `agent_app`) in `apim_extra_allowed_addresses`.
- [ ] The claims API is internal-only, so the gateway cannot reach it yet. Leave `apim_claims_api_url` null until ingress for it is opened to the gateway's public IP (the `public_ip_addresses` output).

### Finish M3: apply the policy change, then run the load test
- [ ] `infra/envs/dev/terraform.tfvars` now lists your public IP in `apim_extra_allowed_addresses`. If it changes (home network), update it and apply again.
- [ ] `make plan ENV=dev` should show 4 policy changes and nothing else, then `make apply ENV=dev`.
- [ ] Export the gateway URL and the per-country keys (the block under "Live checks for Milestone M1"), then `make ingest` and `uv run pytest tests/integration -m integration`.
- [ ] `make load-test ARGS="--report docs/load-test.md"` (defaults: ph at 3 req/s, sg and th at 0.2 req/s, 60 s each; costs a few cents). Needs `GATEWAY_KEY_PH`, `GATEWAY_KEY_SG`, `GATEWAY_KEY_TH`.
- [x] Done 2026-10-26: policy change applied, integration tests and load test run.
- [ ] Then destroy the gateway (`enable_apim = false` and apply, or `make destroy ENV=dev`) to stop the Developer-tier charge.

### Telemetry and the budget controller (M5)
- [ ] `make apply ENV=dev` creates, among other things, a Monitoring Metrics Publisher role for you on Application Insights (needed because key-based ingestion is off), the `budget-state` container and the dashboard workbook (4 tabs). After it, run the app with `APPLICATIONINSIGHTS_CONNECTION_STRING=$(terraform -chdir=infra/envs/dev output -raw application_insights_connection_string)` and `APP_ENV=dev`; spans appear in the `AppDependencies` table about 2-5 minutes later.
- [ ] To try the budget controller: `make package-budget`, then in `terraform.tfvars` set `enable_budget_function = true` and `budget_function_package = "../../../dist/budget_controller.zip"`, plan and apply. The function uses Flex Consumption (check the region supports it) and runs every 15 minutes.
- [ ] Give `agent_app` the state: set `BUDGET_STATE_ACCOUNT_URL` (the container app gets it from Terraform; locally use the storage account's blob endpoint, and you need Storage Blob Data Reader).
- [ ] To force a country over its budget for a test: lower `monthly_budget_usd` in that country's pack (for example `ph.yaml` to 0.01), repackage, redeploy, wait for the next run, and expect that country's state to flip, an alert email, and low-risk turns to be routed small while risky ones hand off. Put the budget back afterwards.
- [ ] Evaluation results can be pushed into the quality tab with `python tools/push_eval_summary.py` (needs the connection string and the Monitoring Metrics Publisher role).

## Cloudflare Access (before exposing anything publicly)
- [ ] Have a Cloudflare zone for the hostname and add a proxied DNS record for the app.
- [ ] In Cloudflare Zero Trust, create a self-hosted Access application for that hostname with a policy that allows only the people you want (for example by email). Note the team domain and the application audience (AUD) tag; the app or APIM will use them to check the `Cf-Access-Jwt-Assertion` token.
- [ ] Do this before F-029 is applied, and keep Container Apps and APIM restricted to Cloudflare IP ranges so Access cannot be bypassed.
- [ ] Refresh the IP ranges from https://www.cloudflare.com/ips-v4 now and then (the last check, 2026-10-25, matched the `sqai-alz` list).
- [ ] Decide if Terraform should manage the Cloudflare side too (needs the `cloudflare` provider added to the allowed list).

### GitHub / CI (deferred)
CI/CD is not needed for now. Skip OIDC, repo secrets and the first-PR check until you want it back; the workflows in `.github/workflows/` are inert without a GitHub repo.

### Azure checks (F-012, F-014, F-032)
- [ ] Confirm model availability and quota in each country's region (for example `japaneast`) before relying on it.
- [ ] Replace the placeholder prices in `components/country_packs/models.yaml` with current Azure pricing.
- [x] APIM tier: Developer (ADR-001). Confirm its monthly price on the Azure pricing page.

### App and web UI (F-025, F-029)
- [x] No sign-in for now, so no Entra ID app registration is needed. Run the apps locally only and do not expose them publicly.
- [ ] Choose the container registry. GitHub Container Registry was the default, but without GitHub use Azure Container Registry (the `registry` variable allows it; it bills a small daily fee).

### Quality and routing (F-035, F-038, F-050)
- [ ] Have native speakers review golden cases and set `reviewed_by_native: true` only for those.
- [ ] Review `results/routing.proposed.yaml` and copy it to `components/router/routing.yaml` yourself.
- [ ] Decide whether the semantic cache (hourly Redis cost) stays on after it is measured.

### Cleanup
- [ ] `make destroy ENV=dev` when you stop working, to stop spend. A budget only alerts; it does not stop spending.
