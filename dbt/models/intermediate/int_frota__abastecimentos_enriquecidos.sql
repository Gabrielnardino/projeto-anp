with

abastecimentos as (
    select * from {{ ref('stg_frota__abastecimentos') }}
),

precos as (
    select * from {{ ref('int_anp__precos_semanais') }}
),

com_anterior as (
    select
        *,
        date_trunc('week', data)::date as semana,
        lag(odometro_km) over por_veiculo as odometro_anterior_km,
        lag(data_hora) over por_veiculo as data_hora_anterior
    from abastecimentos
    window por_veiculo as (partition by placa order by data_hora, id_abastecimento)
)

select
    com_anterior.id_abastecimento,
    com_anterior.data_hora,
    com_anterior.data,
    com_anterior.placa,
    com_anterior.matricula,
    com_anterior.cnpj_posto,
    com_anterior.produto,
    com_anterior.litros,
    com_anterior.valor_litro,
    com_anterior.valor_total,
    com_anterior.odometro_km,
    com_anterior.odometro_anterior_km,
    com_anterior.odometro_km - com_anterior.odometro_anterior_km as km_desde_anterior,
    extract(
        epoch from com_anterior.data_hora - com_anterior.data_hora_anterior
    ) / 60 as minutos_desde_anterior,
    referencia.semana as semana_referencia_anp,
    referencia.preco_medio as preco_anp_posto,
    referencia.mediana_municipio as preco_anp_mediana_municipio
from com_anterior
-- preço que a ANP coletou no próprio posto na semana do abastecimento; se o posto não foi
-- pesquisado naquela semana, vale a coleta mais recente dentro da janela de validade
left join lateral (
    select
        precos.semana,
        precos.preco_medio,
        precos.mediana_municipio
    from precos
    where
        precos.cnpj = com_anterior.cnpj_posto
        and precos.produto = com_anterior.produto
        and precos.semana between
        com_anterior.semana - 7 * {{ var('semanas_validade_preco_anp') }}
        and com_anterior.semana
    order by precos.semana desc
    limit 1
) as referencia on true
