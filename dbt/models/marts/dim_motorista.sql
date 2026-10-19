select
    matricula,
    nome,
    base,
    data_admissao
from {{ ref('stg_frota__motoristas') }}
