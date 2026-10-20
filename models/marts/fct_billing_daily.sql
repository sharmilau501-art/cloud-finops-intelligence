-- Grain: one application + owning team + usage date.
-- Keep the shared/platform application intact: NO allocation in Phase 3.
select
    usage_date,
    application,
    team,
    cast(sum(unblended_cost_usd) as decimal(18, 2)) as billed_cost_usd,
    count(*) as billing_line_items
from {{ ref('stg_billing') }}
group by 1, 2, 3
