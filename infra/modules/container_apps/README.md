# container_apps

Azure Container Apps environment (consumption plan) with the three apps: `agent_app`, `claims_api` and `web_ui`. Each app has its own image and its own user-assigned managed identity. Nothing here is applied until you turn it on in an env (`enable_container_apps = true`).

## What it creates

- Environment `cae-<prefix>` logging to the Log Analytics workspace.
- One user-assigned identity per app. They are created first and given their roles before the apps start, so Key Vault secrets can be read on the very first revision.
- `agent_app` (port 8000, public) with roles: Search Index Data Reader, Cognitive Services OpenAI User, Monitoring Metrics Publisher and Key Vault Secrets User.
- `claims_api` (port 8001, **internal only**, reached by `agent_app` at its `.internal.` address) with only Key Vault Secrets User.
- `web_ui` (port 80, public). Its nginx writes `config.json` at start from `API_BASE_URL`, so no address or secret is baked into the bundle.
- The approval signing key is a Key Vault secret, passed to `agent_app` and `claims_api` as a secret reference (never a plain value) and never to `web_ui`.

## Safety rules built in

- **No quiet public exposure.** There is no user sign-in, so the module refuses to plan unless `allowed_ip_ranges` is set (normally Cloudflare's published IPv4 ranges, with Cloudflare Access in front) or you set `acknowledge_unrestricted_ingress = true` knowing anyone could then chat, spend tokens and approve claims. Rules are Allow-only, so everything else is denied.
- **One replica for the stateful apps.** `agent_app` remembers used approval tokens and `claims_api` holds drafts in memory, so both are pinned to exactly one replica and never scale out. `web_ui` may scale to zero.
- App names are shortened to fit Azure's 32 character limit.

## Inputs

Required: `name_prefix`, `location`, `resource_group_name`, `tags`, `log_analytics_workspace_id`, `images`, `key_vault_id`, `approval_signing_key_secret_id`, `search_service_id`, `application_insights_id`, `gateway_url`, `gateway_key_secret_ids` (Key Vault secret per country), `search_endpoint`.

Optional: `registry_server` (private registry; grant AcrPull to the principals in `identities`), `claims_api_url` and `claims_key_secret_id` (to send claims calls through the gateway), `allowed_ip_ranges`, `acknowledge_unrestricted_ingress`, `min_replicas`, `cpu`, `memory`.

## Outputs

`environment_id`, `urls` (the apps' addresses; `claims_api` is internal), `identities` (id, principal ID, client ID per app).

## Images

`make build C=agent_app`, `C=claims_api` and `C=web_ui` build `kalayaan-<app>:dev` locally (context is the repo root). Push them to a registry yourself and pass the full references in `images`. The images must be pullable by Container Apps: public, or in a private registry with `registry_server` set and AcrPull granted.

## Tests

`terraform init && terraform test` (mocked provider, 12 runs).
