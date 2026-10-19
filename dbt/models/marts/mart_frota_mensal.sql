with

abastecimentos as (
    select * from {{ ref('fct_abastecimento') }}
),

veiculos as (
    select * from {{ ref('dim_veiculo') }}
),

mensal as (
    select
        placa,
        date_trunc('month', data)::date as mes,
        count(*) as abastecimentos,
        sum(litros) as litros,
        sum(valor_total) as valor_total,
        -- odômetro "telescópico": erros de digitação se anulam na soma do mês
        sum(km_desde_anterior) as km_rodados,
        sum(litros) filter (where km_desde_anterior is not null) as litros_com_km,
        sum(pago_acima_anp_rs) as pago_acima_anp_rs,
        count(*) filter (
            where
            alerta_sobrepreco
            or alerta_consumo_anomalo
            or alerta_litros_acima_tanque
            or alerta_abastecimento_duplicado
            or alerta_odometro_regressivo
        ) as abastecimentos_com_alerta
    from abastecimentos
    group by placa, mes
)

select
    mensal.mes,
    mensal.placa,
    veiculos.base,
    veiculos.marca,
    veiculos.modelo,
    veiculos.km_por_litro_ref,
    mensal.abastecimentos,
    mensal.abastecimentos_com_alerta,
    mensal.litros,
    mensal.valor_total,
    mensal.km_rodados,
    mensal.pago_acima_anp_rs,
    round(mensal.km_rodados / nullif(mensal.litros_com_km, 0), 3) as km_por_litro,
    round(mensal.valor_total / nullif(mensal.km_rodados, 0), 3) as custo_por_km
from mensal
inner join veiculos on mensal.placa = veiculos.placa
