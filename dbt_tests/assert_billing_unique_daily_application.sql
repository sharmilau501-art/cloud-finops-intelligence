-- FAIL when source ownership creates ambiguous day/application facts.
select usage_date, application, count(*) as duplicate_count
from {{ ref('fct_billing_daily') }}
group by 1, 2
having count(*) > 1
