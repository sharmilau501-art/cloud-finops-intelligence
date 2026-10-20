-- All billed dollars must appear in the fully loaded mart for EVERY date.
with billed as (
    select usage_date, sum(billed_cost_usd) as total_billed_usd
    from {{ ref('fct_billing_daily') }} group by 1
), allocated as (
    select usage_date, sum(fully_loaded_cost_usd) as total_allocated_usd
    from {{ ref('fct_shared_cost_allocation_daily') }} group by 1
)
select coalesce(b.usage_date, a.usage_date) as usage_date,
       b.total_billed_usd, a.total_allocated_usd
from billed b full outer join allocated a on b.usage_date = a.usage_date
where b.usage_date is null or a.usage_date is null
   or abs(b.total_billed_usd - a.total_allocated_usd) > 0.005
