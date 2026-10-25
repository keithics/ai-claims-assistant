locals {
  prefix        = join("-", compact([var.project_name, var.env, var.country]))
  compact       = replace(local.prefix, "-", "")
  suffix_len    = length(var.unique_suffix)
  hyphen_suffix = var.unique_suffix == "" ? "" : "-${var.unique_suffix}"

  tags = merge(
    {
      project     = var.project_name
      env         = var.env
      owner       = var.owner
      cost_center = var.cost_center
    },
    var.country == null ? {} : { country = var.country },
  )

  storage_account = "st${substr(local.compact, 0, 22 - local.suffix_len)}${var.unique_suffix}"
  key_vault       = replace("kv-${substr(local.prefix, 0, 20 - length(local.hyphen_suffix))}${local.hyphen_suffix}", "/-+$/", "")
  search_service  = replace("srch-${substr(local.prefix, 0, 55 - length(local.hyphen_suffix))}${local.hyphen_suffix}", "/-+$/", "")

  names = {
    resource_group       = "rg-${local.prefix}"
    log_analytics        = "log-${local.prefix}"
    application_insights = "appi-${local.prefix}"
    action_group         = "ag-${local.prefix}"
    consumption_budget   = "budget-${local.prefix}"
    ai_services          = replace("ais-${substr(local.prefix, 0, 59 - length(local.hyphen_suffix))}${local.hyphen_suffix}", "/-+$/", "")
    foundry_project      = "proj-${local.prefix}"
    api_management       = "apim-${local.prefix}"
    container_app_env    = "cae-${local.prefix}"
    function_app         = "func-${local.prefix}"
    virtual_network      = "vnet-${local.prefix}"
    managed_identity     = "id-${local.prefix}"
    storage_account      = local.storage_account
    key_vault            = local.key_vault
    search_service       = local.search_service
  }
}
