{#- tipo de alerta: estimativa do prejuízo em R$ -#}
{%- set regras = {
    'sobrepreco': 'litros * (valor_litro - preco_anp_posto)',
    'consumo_anomalo': '(litros - km_desde_anterior / km_por_litro_ref) * valor_litro',
    'litros_acima_tanque': '(litros - capacidade_tanque_l) * valor_litro',
    'abastecimento_duplicado': 'valor_total',
    'odometro_regressivo': '0',
} -%}

with

abastecimentos as (
    select * from {{ ref('fct_abastecimento') }}
)

{% for tipo, impacto in regras.items() %}
    select
        id_abastecimento,
        data_hora,
        data,
        placa,
        matricula,
        cnpj_posto,
        '{{ tipo }}' as tipo_alerta,
        valor_total,
        round({{ impacto }}, 2) as impacto_estimado_rs
    from abastecimentos
    where alerta_{{ tipo }}
    {% if not loop.last %}union all{% endif %}
{% endfor %}
