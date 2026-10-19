with

origem as (
    select * from {{ source('raw', 'anp_precos') }}
),

tipado as (
    select
        competencia,
        regexp_replace(cnpj, '\D', '', 'g') as cnpj,
        trim(revenda) as revenda,
        trim(bandeira) as bandeira,
        regiao as regiao_sigla,
        uf,
        municipio,
        concat_ws(', ', trim(nome_rua), nullif(trim(numero_rua), '')) as endereco,
        trim(bairro) as bairro,
        cep,
        to_date(data_coleta, 'DD/MM/YYYY') as data_coleta,
        replace(valor_venda, ',', '.')::numeric(10, 3) as valor_venda,
        unidade_medida,
        _carregado_em,
        -- na pesquisa o S500 aparece só como "DIESEL"
        case produto when 'DIESEL' then 'DIESEL S500' else produto end as produto
    from origem
),

deduplicado as (
    -- a ANP publica algumas coletas repetidas (mesmo posto, produto e dia)
    select
        *,
        row_number() over (
            partition by cnpj, produto, data_coleta order by _carregado_em desc
        ) as ordem
    from tipado
)

select
    cnpj,
    produto,
    data_coleta,
    valor_venda,
    unidade_medida,
    revenda,
    bandeira,
    regiao_sigla,
    uf,
    municipio,
    endereco,
    bairro,
    cep,
    competencia,
    _carregado_em
from deduplicado
where ordem = 1
