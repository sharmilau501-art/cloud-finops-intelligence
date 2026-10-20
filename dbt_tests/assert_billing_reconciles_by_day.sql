-- FAIL if modeling changes the total daily dollars loaded by ingestion.
with raw_daily as (
    select usage_date, sum(unblended_cost_usd) as amount
    from {{ source('raw', 'billing') }}
    group by 1
), mart_daily as (
    select usage_date, sum(billed_cost_usd) as amount
    from {{ ref('fct_billing_daily') }}
    group by 1
)
select
    coalesce(r.usage_date, m.usage_date) as usage_date,
    r.amount as raw_usd,
    m.amount as modeled_usd
from raw_daily r
full outer join mart_daily m on r.usage_date = m.usage_date
where r.amount is null or m.amount is null or abs(r.amount - m.amount) > 0.005
