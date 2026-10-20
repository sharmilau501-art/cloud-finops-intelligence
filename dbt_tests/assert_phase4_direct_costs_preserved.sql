select a.usage_date, a.application,
       a.direct_cost_usd as allocated_mart_direct_usd,
       m.direct_cost_usd as original_mart_direct_usd
from {{ ref('fct_shared_cost_allocation_daily') }} a
full outer join {{ ref('mart_unit_economics_daily') }} m
  on a.usage_date = m.usage_date and a.application = m.application
where a.application is null or m.application is null
   or abs(a.direct_cost_usd - m.direct_cost_usd) > 0.005
