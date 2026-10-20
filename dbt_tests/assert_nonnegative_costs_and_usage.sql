select usage_date, application
from {{ ref('fct_billing_daily') }}
where billed_cost_usd < 0
union all
select usage_date, application
from {{ ref('fct_product_usage_daily') }}
where product_requests < 0 or active_users < 0
union all
select usage_date, application
from {{ ref('mart_unit_economics_daily') }}
where direct_cost_usd < 0 or direct_cost_per_1k_requests_usd < 0
