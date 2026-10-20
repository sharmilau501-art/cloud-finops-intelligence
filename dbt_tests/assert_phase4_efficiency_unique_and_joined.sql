select k.usage_date, k.application
from {{ ref('mart_k8s_efficiency_daily') }} k
left join {{ ref('fct_shared_cost_allocation_daily') }} a
  on k.usage_date = a.usage_date and k.application = a.application
where a.application is null or k.fully_loaded_cost_usd is null
union all
select usage_date, application
from {{ ref('mart_k8s_efficiency_daily') }}
group by 1,2 having count(*) > 1
