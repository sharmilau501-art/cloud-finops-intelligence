-- Preliminary DIRECT cost per 1,000 product requests; shared costs excluded.
-- Shared allocation and fully loaded unit economics are Phase 4 work.
select
    usage.usage_date,
    usage.application,
    usage.product_requests,
    usage.active_users,
    coalesce(bill.billed_cost_usd, cast(0 as decimal(18, 2))) as direct_cost_usd,
    case
      when usage.product_requests > 0 then
        round(coalesce(bill.billed_cost_usd, cast(0 as decimal(18, 2))) * 1000.0
              / usage.product_requests, 4)
      else null
    end as direct_cost_per_1k_requests_usd
from {{ ref('fct_product_usage_daily') }} as usage
left join {{ ref('fct_billing_daily') }} as bill
  on usage.usage_date = bill.usage_date
 and usage.application = bill.application
 and bill.application <> 'shared'
