-- Compara os alertas com as anomalias injetadas pelo gerador (o "gabarito").
-- Só faz sentido com dados simulados, mas mostra como as regras se comportam.
with

alertas as (
    select
        id_abastecimento,
        tipo_alerta as tipo,
        true as alertou
    from {{ ref('mart_alertas') }}
),

gabarito as (
    select
        id_abastecimento,
        tipo_anomalia as tipo,
        true as anomalo
    from {{ ref('stg_frota__gabarito') }}
),

cruzado as (
    select
        coalesce(alertas.tipo, gabarito.tipo) as tipo,
        coalesce(alertas.alertou, false) as alertou,
        coalesce(gabarito.anomalo, false) as anomalo
    from alertas
    full outer join gabarito
        on
            alertas.id_abastecimento = gabarito.id_abastecimento
            and alertas.tipo = gabarito.tipo
),

contagens as (
    select
        tipo,
        count(*) filter (where alertou and anomalo) as verdadeiros_positivos,
        count(*) filter (where alertou and not anomalo) as falsos_positivos,
        count(*) filter (where not alertou and anomalo) as falsos_negativos
    from cruzado
    group by tipo
)

select
    *,
    round(
        verdadeiros_positivos::numeric / nullif(verdadeiros_positivos + falsos_positivos, 0), 3
    ) as precisao,
    round(
        verdadeiros_positivos::numeric / nullif(verdadeiros_positivos + falsos_negativos, 0), 3
    ) as recall
from contagens
