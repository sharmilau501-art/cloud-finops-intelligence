-- One row per day and consumer application.
-- Shared platform cost is allocated across consumers by daily request volume.
-- Integer cent allocation + largest remainder prevents rounding leakage.
-- If ALL consumer request counts are zero, allocate equally for that day.
with consumers as (
    select
        p.usage_date,
        p.application,
        p.product_requests,
        coalesce(b.billed_cost_usd, cast(0 as decimal(18,2))) as direct_cost_usd,
        sum(p.product_requests) over (partition by p.usage_date) as daily_requests,
        count(*) over (partition by p.usage_date) as consumer_count
    from {{ ref('fct_product_usage_daily') }} p
    left join {{ ref('fct_billing_daily') }} b
      on p.usage_date = b.usage_date and p.application = b.application
      and b.application <> 'shared'
),
shared_pool as (
    select usage_date, cast(sum(billed_cost_usd) as decimal(18,2)) as shared_pool_usd
    from {{ ref('fct_billing_daily') }}
    where application = 'shared'
    group by 1
),
weights as (
    select
        c.*,
        coalesce(s.shared_pool_usd, cast(0 as decimal(18,2))) as shared_pool_usd,
        cast(round(coalesce(s.shared_pool_usd, 0) * 100, 0) as bigint) as shared_pool_cents,
        case when c.daily_requests > 0 then c.product_requests else 1 end as allocation_weight,
        case when c.daily_requests > 0 then c.daily_requests else c.consumer_count end as total_weight,
        case when c.daily_requests > 0 then 'request_share' else 'equal_share_zero_requests' end as allocation_method
    from consumers c
    left join shared_pool s using (usage_date)
),
quotas as (
    select
        *,
        (cast(shared_pool_cents as double) * allocation_weight / nullif(total_weight, 0)) as quota_cents
    from weights
),
base_cents as (
    select *,
        cast(floor(quota_cents) as bigint) as initial_cents,
        quota_cents - floor(quota_cents) as fractional_cents
    from quotas
),
ranked as (
    select *,
        shared_pool_cents - sum(initial_cents) over (partition by usage_date) as residual_cents,
        row_number() over (partition by usage_date order by fractional_cents desc, application asc) as residual_rank
    from base_cents
),
allocation as (
    select
        *,
        initial_cents + case when residual_rank <= residual_cents then 1 else 0 end as allocated_shared_cents
    from ranked
)
select
    usage_date,
    application,
    product_requests,
    direct_cost_usd,
    shared_pool_usd,
    allocation_method,
    cast(allocated_shared_cents / 100.0 as decimal(18,2)) as allocated_shared_cost_usd,
    cast(direct_cost_usd + allocated_shared_cents / 100.0 as decimal(18,2)) as fully_loaded_cost_usd,
    case when product_requests > 0 then
        round((direct_cost_usd + allocated_shared_cents / 100.0) * 1000.0 / product_requests, 4)
      else null end as fully_loaded_cost_per_1k_requests_usd
from allocation
