select
    *,
    round(preco_medio / nullif(mediana_municipio, 0) - 1, 4) as posto_vs_municipio_pct
from {{ ref('int_anp__precos_semanais') }}
