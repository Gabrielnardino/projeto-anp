select
    placa,
    marca,
    modelo,
    ano_fabricacao,
    capacidade_tanque_l,
    km_por_litro_ref,
    produto,
    base
from {{ source('raw', 'frota_veiculos') }}
