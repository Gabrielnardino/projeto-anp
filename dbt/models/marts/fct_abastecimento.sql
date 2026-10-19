with

abastecimentos as (
    select * from {{ ref('int_frota__abastecimentos_enriquecidos') }}
),

veiculos as (
    select * from {{ ref('stg_frota__veiculos') }}
),

metricas as (
    select
        abastecimentos.*,
        veiculos.capacidade_tanque_l,
        veiculos.km_por_litro_ref,
        case
            when abastecimentos.km_desde_anterior > 0
                then round(abastecimentos.km_desde_anterior / abastecimentos.litros, 3)
        end as km_por_litro,
        round(abastecimentos.valor_litro / abastecimentos.preco_anp_posto - 1, 4)
            as sobrepreco_pct,
        round(
            greatest(abastecimentos.valor_litro - abastecimentos.preco_anp_posto, 0)
            * abastecimentos.litros,
            2
        ) as pago_acima_anp_rs
    from abastecimentos
    inner join veiculos on abastecimentos.placa = veiculos.placa
),

regras as (
    select
        *,
        coalesce(sobrepreco_pct > {{ var('limite_sobrepreco_pct') }}, false)
            as alerta_sobrepreco,
        litros > capacidade_tanque_l as alerta_litros_acima_tanque,
        coalesce(minutos_desde_anterior < {{ var('limite_minutos_duplicado') }}, false)
            as alerta_abastecimento_duplicado,
        coalesce(odometro_km < odometro_anterior_km, false) as alerta_odometro_regressivo
    from metricas
)

select
    *,
    -- km/l baixo só vira alerta quando não é efeito colateral de outro problema já apontado
    coalesce(km_por_litro < km_por_litro_ref * {{ var('limite_consumo_pct_ref') }}, false)
    and not (alerta_litros_acima_tanque or alerta_abastecimento_duplicado)
        as alerta_consumo_anomalo
from regras
