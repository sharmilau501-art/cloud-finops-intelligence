-- Synthetic seed has one telemetry snapshot per day/app.
-- Means describe sample averages, not time-weighted capacity utilization.
select
    usage_date,
    application,
    avg(cpu_utilization_pct) as avg_cpu_utilization_pct,
    avg(memory_utilization_pct) as avg_memory_utilization_pct,
    max(requested_cpu_cores) as requested_cpu_cores,
    max(requested_memory_gib) as requested_memory_gib,
    count(*) as telemetry_samples
from {{ ref('stg_k8s_metrics') }}
group by 1, 2
