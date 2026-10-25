output "name_prefix" {
  value       = local.prefix
  description = "Base prefix: project-env, plus -country when set."
}

output "names" {
  value       = local.names
  description = "Resource names by type, following Azure length and character rules."
}

output "tags" {
  value       = local.tags
  description = "Required tags: project, env, owner, cost_center, and country when set."
}
