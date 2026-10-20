-- No paid application can disappear simply because it has no product traffic row.
select b.usage_date, b.application
from {{ ref('fct_billing_daily') }} b
left join {{ ref('fct_shared_cost_allocation_daily') }} a
  on b.usage_date = a.usage_date and b.application = a.application
where b.application <> 'shared' and a.application is null
