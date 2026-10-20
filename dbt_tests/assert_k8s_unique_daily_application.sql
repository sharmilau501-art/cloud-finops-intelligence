select usage_date, application, count(*) as duplicate_count
from {{ ref('fct_k8s_daily') }}
group by 1, 2
having count(*) > 1
