-- Regressão das regras de auditoria: cada regra precisa achar a maioria das anomalias.
select *
from {{ ref('mart_avaliacao_regras') }}
where recall < 0.7
