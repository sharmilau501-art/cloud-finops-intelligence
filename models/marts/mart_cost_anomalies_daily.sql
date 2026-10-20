-- Baseline is seven PRIOR observed daily entries per application.
-- A flag requires >=7 observations and cost > 1.25x baseline by default.
with baselines as (
    select
        usage_date,
        application,
        fully_loaded_cost_usd,
        count(*) over (
          partition by application order by usage_date
          rows between 7 preceding and 1 preceding
        ) as prior_observations,
        avg(fully_loaded_cost_usd) over (
          partition by application order by usage_date
          rows between 7 preceding and 1 preceding
        ) as prior_7_observation_avg_usd
    from {{ ref('fct_shared_cost_allocation_daily') }}
)
select
    *,
    case when prior_7_observation_avg_usd > 0 then
      round(fully_loaded_cost_usd / prior_7_observation_avg_usd, 4)
    else null end as cost_vs_baseline_ratio,
    (
      prior_observations >= 7
      and prior_7_observation_avg_usd > 0
      and fully_loaded_cost_usd > prior_7_observation_avg_usd * {{ var('cost_anomaly_ratio_threshold', 1.25) }}
    ) as cost_anomaly_flag
from baselines
