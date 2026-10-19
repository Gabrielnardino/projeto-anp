from datetime import datetime, timedelta

from airflow.sdk import dag, task
from ativos import ANP_PRECOS


@dag(
    schedule="0 6 * * 1",  # semanal; a ANP publica o mês fechado sem data fixa
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["anp", "ingestao"],
    doc_md="""
    Sincroniza a Série Histórica de Preços de Combustíveis da ANP (diesel + GNV):
    baixa os meses que faltam desde 2024-01 e recarrega os 2 mais recentes,
    porque a ANP às vezes republica. Cada competência é substituída inteira (idempotente).
    """,
)
def coleta_anp():
    @task(outlets=[ANP_PRECOS], retries=3, retry_delay=timedelta(minutes=10))
    def sincronizar() -> list[str]:
        from pipeline import anp

        return [str(c) for c in anp.sincronizar()]

    sincronizar()


coleta_anp()
