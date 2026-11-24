output "project_id" {
  description = "Google Cloud project"
  value       = var.project_id
}

output "dataset_id" {
  description = "Managed BigQuery dataset"
  value       = google_bigquery_dataset.finops.dataset_id
}

output "billing_daily_table" {
  description = "Billing daily table ID"
  value       = google_bigquery_table.billing_daily.id
}

output "app_daily_table" {
  description = "Application daily table ID"
  value       = google_bigquery_table.app_daily.id
}

output "dataset_location" {
  description = "BigQuery dataset location"
  value       = google_bigquery_dataset.finops.location
}
