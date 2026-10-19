with

precos as (
    select * from {{ ref('stg_anp__precos') }}
),

ultima_coleta as (
    select distinct on (cnpj)
        cnpj,
        revenda,
        bandeira,
        endereco,
        bairro,
        cep,
        municipio,
        uf,
        regiao_sigla
    from precos
    order by cnpj asc, data_coleta desc
),

historico as (
    select
        cnpj,
        min(data_coleta) as primeira_coleta,
        max(data_coleta) as ultima_coleta,
        count(distinct bandeira) as bandeiras_no_periodo
    from precos
    group by cnpj
)

select
    ultima_coleta.*,
    historico.primeira_coleta,
    historico.ultima_coleta,
    historico.bandeiras_no_periodo
from ultima_coleta
inner join historico on ultima_coleta.cnpj = historico.cnpj
