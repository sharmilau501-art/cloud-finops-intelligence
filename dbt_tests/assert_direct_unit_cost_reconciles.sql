-- The direct-cost mart must not silently include the shared platform cost.
select
    m.usage_date, m.application, m.direct_cost_usd,
    coalesce(b.billed_cost_usd, cast(0 as decimal(18, 2))) as expected_direct_cost
from {{ ref('mart_unit_economics_daily') }} m
left join {{ ref('fct_billing_daily') }} b
  on m.usage_date = b.usage_date
 and m.application = b.application
where abs(m.direct_cost_usd - coalesce(b.billed_cost_usd, cast(0 as decimal(18, 2)))) > 0.005
