# country_packs

Per-market YAML packs, the model catalog with prices, a Pydantic schema and a loader. Adding a market needs only a new `countries/<code>.yaml` and documents under `rag/data/policies/<code>/`, never code. May be imported by every component.

## Public interface

- `load_country_packs(dir=None) -> dict[str, CountryPack]`, `load_country_pack(path)`: load and validate packs.
- `load_model_catalog(path=None) -> ModelCatalog`, `prices_from_catalog(catalog) -> dict[str, shared.ModelPrice]`: deployments, tiers and prices for `shared.cost_usd`.
- `load_all(root=None)`: both, for startup. Any problem raises `PackValidationError` naming the file and the field, so a bad pack stops the app at startup.
- `CountryPack`, `ModelCatalog`, `DeploymentEntry`, `PriceEntry`: the schema.

The default root is this component's folder; set `COUNTRY_PACKS_DIR` to point elsewhere (for example in a container image).

## Rules the schema enforces

`code` is two lowercase letters and equals the file name; `search_filter` is `country eq '<code>'`; the budget and retention are positive; tiers are `small` and `large`; unknown keys are rejected; the catalog must hold at least one `small` and one `large` deployment.

## Prices are placeholders

`models.yaml` prices (USD per 1M tokens) and model names are placeholders. Update them from Azure pricing before trusting any cost figure.
