select
    cast(usage_date as date) as usage_date,
    lower(trim(application)) as application,
    lower(trim(namespace)) as namespace,
    cast(cpu_utilization_pct as double) as cpu_utilization_pct,
    cast(memory_utilization_pct as double) as memory_utilization_pct,
    cast(requested_cpu_cores as double) as requested_cpu_cores,
    cast(requested_memory_gib as double) as requested_memory_gib
from {{ source('raw', 'k8s_metrics') }}
