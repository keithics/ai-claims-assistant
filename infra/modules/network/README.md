# network

A virtual network with a `private-endpoints` subnet, an `apps` subnet and the private DNS zones (linked to the network) for the services this project uses behind private endpoints. Used only when `enable_private_networking = true`.

**Cost:** the network and the DNS zones are cheap; each private endpoint in `private_endpoints` bills by the hour plus data processed.

Required inputs: `name_prefix`, `location`, `resource_group_name`, `tags`. Optional: `address_space`, `subnets` (must contain `private-endpoints`), `private_dns_zones`.

Outputs: `vnet_id`, `subnet_ids`, `private_dns_zone_ids`.
