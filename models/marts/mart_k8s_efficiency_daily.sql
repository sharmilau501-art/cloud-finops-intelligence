-- Daily illustrative review flags, not measured waste or guaranteed savings.
-- Source telemetry is one snapshot per application/day, not continuous data.
select
    k.usage_date,
    k.application,
    k.avg_cpu_utilization_pct,
    k.avg_memory_utilization_pct,
    k.requested_cpu_cores,
    k.requested_memory_gib,
    k.telemetry_samples,
    a.fully_loaded_cost_usd,
    (
      k.avg_cpu_utilization_pct < {{ var('low_cpu_threshold_pct', 25) }}
      and k.avg_memory_utilization_pct < {{ var('low_memory_threshold_pct', 35) }}
    ) as low_utilization_review_flag,
    case
      when k.avg_cpu_utilization_pct < {{ var('low_cpu_threshold_pct', 25) }}
       and k.avg_memory_utilization_pct < {{ var('low_memory_threshold_pct', 35) }}
      then 'review_requested_resources'
      else 'no_flag'
    end as suggested_review
from {{ ref('fct_k8s_daily') }} k
left join {{ ref('fct_shared_cost_allocation_daily') }} a
  on k.usage_date = a.usage_date and k.application = a.application
