select
    id_abastecimento,
    tipo_anomalia
from {{ source('raw', 'frota_gabarito') }}
