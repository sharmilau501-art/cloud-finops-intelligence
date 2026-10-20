select
    application,
    max(team) as owning_team,
    case when application = 'shared' then true else false end as is_shared_platform
from {{ ref('stg_billing') }}
group by 1
