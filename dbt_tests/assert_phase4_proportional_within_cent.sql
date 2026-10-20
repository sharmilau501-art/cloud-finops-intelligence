-- Request-share allocations should be within one cent of exact proportional quota.
with a as (
 select *, sum(product_requests) over(partition by usage_date) as daily_requests
 from {{ ref('fct_shared_cost_allocation_daily') }}
)
select usage_date, application, allocated_shared_cost_usd,
       shared_pool_usd * product_requests / nullif(daily_requests,0) as exact_share
from a
where daily_requests > 0
  and abs(allocated_shared_cost_usd
          - shared_pool_usd * product_requests / daily_requests) > 0.010001
