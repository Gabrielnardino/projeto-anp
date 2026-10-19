select
    id_abastecimento,
    placa,
    matricula,
    data_hora,
    data_hora::date as data,
    regexp_replace(cnpj_posto, '\D', '', 'g') as cnpj_posto,
    produto,
    litros,
    valor_litro,
    valor_total,
    odometro_km
from {{ source('raw', 'frota_abastecimentos') }}
