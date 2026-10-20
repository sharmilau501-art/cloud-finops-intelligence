select
    cast(usage_date as date) as usage_date,
    trim(line_item_id) as line_item_id,
    trim(line_item_product_code) as cloud_product,
    trim(resource_id) as resource_id,
    lower(trim(application)) as application,
    lower(trim(team)) as team,
    lower(trim(cost_category)) as cost_category,
    cast(unblended_cost_usd as decimal(18, 2)) as unblended_cost_usd,
    cast(usage_quantity as double) as usage_quantity,
    trim(usage_unit) as usage_unit
from {{ source('raw', 'billing') }}
