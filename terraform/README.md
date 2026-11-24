# FinOps Infrastructure as Code

Terraform configuration for managing the existing
Google BigQuery infrastructure used by the FinOps
Cloud Intelligence platform.

## Managed Resources

- BigQuery dataset: finops_demo
- BigQuery table: billing_daily
- BigQuery table: app_daily

## Technology Stack

- Terraform 1.17.2
- Google Terraform Provider 7.46.2
- Google BigQuery
- GitHub Actions
- JSON table schemas

## Infrastructure Features

- Parameterized project and dataset configuration
- Version-controlled BigQuery schemas
- Local Terraform state management
- Existing-resource adoption using Terraform import
- Resource deletion protection
- Dataset expiration configuration
- Locked provider dependencies
- Automated infrastructure configuration validation

## Local Validation

From the terraform directory:

    terraform init
    terraform fmt -check -recursive
    terraform validate
    terraform state list
    terraform plan

## Verified Results

- Existing resources imported: 3
- Resources to create: 0
- Resources to modify: 0
- Resources to destroy: 0
- Terraform configuration validation: PASS
- Infrastructure plan: No changes

Existing cloud resources were adopted without
recreating tables or modifying their stored data.

## Security

Terraform state, local variable files, saved plans,
and downloaded provider binaries are excluded
from version control.

Authentication uses Google Application Default
Credentials locally.

GitHub Actions performs credential-free static
validation. Automated infrastructure deployment
is intentionally disabled.

## Limitations

This is a synthetic portfolio project.

BigQuery automatic resource expiration remains
enabled. Terraform deletion protection does not
prevent automatic BigQuery expiration.

Dataset access permissions are excluded from
Terraform change management.

The batch loader uses WRITE_TRUNCATE, which can
replace table schemas. Schema compatibility must
be maintained between the loader and Terraform.

No additional cloud infrastructure was provisioned
during resource adoption.
