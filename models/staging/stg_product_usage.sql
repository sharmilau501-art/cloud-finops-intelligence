select
    cast(usage_date as date) as usage_date,
    lower(trim(application)) as application,
    cast(product_requests as bigint) as product_requests,
    cast(active_users as bigint) as active_users
from {{ source('raw', 'product_usage') }}
