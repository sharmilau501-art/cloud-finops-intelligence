select usage_date, application, count(*) as n
from {{ ref('fct_shared_cost_allocation_daily') }}
group by 1,2 having count(*) <> 1
