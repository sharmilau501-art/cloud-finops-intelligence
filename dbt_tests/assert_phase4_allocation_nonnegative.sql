select * from {{ ref('fct_shared_cost_allocation_daily') }}
where direct_cost_usd < 0
   or allocated_shared_cost_usd < 0
   or fully_loaded_cost_usd < 0
   or product_requests < 0
   or abs(direct_cost_usd + allocated_shared_cost_usd - fully_loaded_cost_usd) > 0.005
