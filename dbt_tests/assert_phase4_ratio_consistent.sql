select * from {{ ref('fct_shared_cost_allocation_daily') }}
where (product_requests = 0 and fully_loaded_cost_per_1k_requests_usd is not null)
   or (product_requests > 0 and (
       fully_loaded_cost_per_1k_requests_usd is null
       or abs(fully_loaded_cost_per_1k_requests_usd
            - round(fully_loaded_cost_usd * 1000.0 / product_requests, 4)) > 0.0001
   ))
