select
    matricula,
    nome,
    base,
    data_admissao
from {{ source('raw', 'frota_motoristas') }}
