variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "dataset_id" {
  description = "FinOps BigQuery dataset"
  type        = string
  default     = "finops_demo"
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "US"
}

variable "default_expiration_ms" {
  description = "Default resource expiration in milliseconds"
  type        = number
  default     = 5184000000
}
