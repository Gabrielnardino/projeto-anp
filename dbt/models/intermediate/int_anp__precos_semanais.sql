{{ config(indexes=[{'columns': ['cnpj', 'produto', 'semana']}]) }}

with

precos as (
    select * from {{ ref('stg_anp__precos') }}
),

por_posto as (
    select
        cnpj,
        produto,
        date_trunc('week', data_coleta)::date as semana,
        uf,
        municipio,
        regiao_sigla,
        -- o posto pode trocar de bandeira; vale a da última coleta da semana
        (array_agg(bandeira order by data_coleta desc))[1] as bandeira,
        avg(valor_venda) as preco_medio,
        count(*) as coletas
    from precos
    group by cnpj, produto, semana, uf, municipio, regiao_sigla
),

por_municipio as (
    select
        uf,
        municipio,
        produto,
        semana,
        percentile_cont(0.5) within group (order by preco_medio) as mediana_municipio,
        count(*) as postos_no_municipio
    from por_posto
    group by uf, municipio, produto, semana
)

select
    por_posto.cnpj,
    por_posto.produto,
    por_posto.semana,
    por_posto.uf,
    por_posto.municipio,
    por_posto.regiao_sigla,
    por_posto.bandeira,
    por_posto.coletas,
    por_municipio.postos_no_municipio,
    round(por_posto.preco_medio, 3) as preco_medio,
    round(por_municipio.mediana_municipio::numeric, 3) as mediana_municipio
from por_posto
inner join por_municipio
    on
        por_posto.uf = por_municipio.uf
        and por_posto.municipio = por_municipio.municipio
        and por_posto.produto = por_municipio.produto
        and por_posto.semana = por_municipio.semana
