# private_endpoints

One private endpoint per entry in `endpoints`, each with a private DNS zone group so the service name resolves to the private address inside the network. Used with `modules/network` when `enable_private_networking = true`.

**Cost:** every private endpoint bills by the hour plus per GB processed. This design uses four (AI Services, AI Search, Blob storage, Key Vault), so leave the flag off for everyday development and turn it on for a test window.

**Limits:** AI Search needs the Basic tier or above for private endpoints; the module's caller refuses to plan the flag with the free tier. When the flag is on, your laptop can no longer reach these services directly (and `make ingest` fails) unless you are on the network, through a VPN or a jump host.

Required inputs: `name_prefix`, `location`, `resource_group_name`, `tags`, `subnet_id`, `endpoints` (resource_id, subresource_name, dns_zone_ids). Output: `endpoint_ids`.
