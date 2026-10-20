with shared as (
    select usage_date, sum(billed_cost_usd) as shared_billed_usd
    from {{ ref('fct_billing_daily') }}
    where application = 'shared' group by 1
), allocated as (
    select usage_date, sum(allocated_shared_cost_usd) as allocated_shared_usd
    from {{ ref('fct_shared_cost_allocation_daily') }} group by 1
)
select coalesce(s.usage_date, a.usage_date) usage_date,
       coalesce(s.shared_billed_usd, 0) shared_billed_usd,
       coalesce(a.allocated_shared_usd, 0) allocated_shared_usd
from shared s full outer join allocated a on s.usage_date = a.usage_date
where abs(coalesce(s.shared_billed_usd, 0) - coalesce(a.allocated_shared_usd, 0)) > 0.005
   or (s.usage_date is not null and a.usage_date is null)
