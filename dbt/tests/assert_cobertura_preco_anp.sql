{{ config(severity='warn') }}
-- Abastecimentos até a última semana publicada pela ANP deveriam ter preço de referência.
-- Muitos nulos indicam problema no cruzamento por CNPJ/produto.
with ultima_semana_anp as (
    select max(semana) as semana from {{ ref('fct_preco_anp_semanal') }}
)

select count(*) filter (where preco_anp_posto is null)::numeric / count(*) as pct_sem_referencia
from {{ ref('fct_abastecimento') }}
where data < (select ultima_semana_anp.semana from ultima_semana_anp)
having count(*) filter (where preco_anp_posto is null)::numeric / count(*) > 0.2
