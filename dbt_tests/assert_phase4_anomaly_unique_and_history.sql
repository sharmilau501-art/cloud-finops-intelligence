select usage_date, application
from {{ ref('mart_cost_anomalies_daily') }}
group by 1,2 having count(*) > 1
union all
select usage_date, application
from {{ ref('mart_cost_anomalies_daily') }}
where prior_observations < 7 and cost_anomaly_flag
