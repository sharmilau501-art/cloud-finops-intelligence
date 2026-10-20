select usage_date, application, count(*) as duplicate_count
from {{ ref('mart_unit_economics_daily') }}
group by 1, 2
having count(*) > 1
