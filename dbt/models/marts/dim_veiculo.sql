select
    placa,
    marca,
    modelo,
    ano_fabricacao,
    capacidade_tanque_l,
    km_por_litro_ref,
    produto,
    base,
    extract(year from current_date)::int - ano_fabricacao as idade_anos
from {{ ref('stg_frota__veiculos') }}
