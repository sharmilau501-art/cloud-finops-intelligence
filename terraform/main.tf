resource "google_bigquery_dataset" "finops" {
  project    = var.project_id
  dataset_id = var.dataset_id
  location   = var.location

  default_table_expiration_ms     = var.default_expiration_ms
  default_partition_expiration_ms = var.default_expiration_ms

  max_time_travel_hours      = "168"
  delete_contents_on_destroy = false

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [access]
  }
}

resource "google_bigquery_table" "billing_daily" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.finops.dataset_id
  table_id   = "billing_daily"

  schema = file("${path.module}/schemas/billing_daily.json")

  deletion_protection = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "app_daily" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.finops.dataset_id
  table_id   = "app_daily"

  schema = file("${path.module}/schemas/app_daily.json")

  deletion_protection = true

  lifecycle {
    prevent_destroy = true
  }
}
