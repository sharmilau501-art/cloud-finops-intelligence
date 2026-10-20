-- Grain: date/application. The seed contains one aggregate per date/app.
select
    usage_date,
    application,
    sum(product_requests) as product_requests,
    sum(active_users) as active_users,
    count(*) as source_records
from {{ ref('stg_product_usage') }}
group by 1, 2
