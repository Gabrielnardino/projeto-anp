-- valor total do abastecimento = litros × preço por litro (tolerância de arredondamento)
select *
from {{ ref('fct_abastecimento') }}
where abs(litros * valor_litro - valor_total) > 0.01
