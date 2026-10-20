with dates as (
    select usage_date from {{ ref('stg_billing') }}
    union
    select usage_date from {{ ref('stg_k8s_metrics') }}
    union
    select usage_date from {{ ref('stg_product_usage') }}
)
select
    usage_date,
    cast(extract(year from usage_date) as integer) as calendar_year,
    cast(extract(month from usage_date) as integer) as calendar_month,
    cast(extract(day from usage_date) as integer) as day_of_month
from dates
