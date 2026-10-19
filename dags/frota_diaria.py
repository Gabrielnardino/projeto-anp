from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task
from ativos import FROTA_ABASTECIMENTOS

FUSO = ZoneInfo("America/Sao_Paulo")


@dag(
    schedule="0 1 * * *",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    tags=["frota", "ingestao"],
    doc_md="""
    Simula a exportação diária do sistema de frota: gera os abastecimentos do dia anterior
    em postos reais da pesquisa ANP. Reprocessar um dia gera exatamente as mesmas linhas.
    """,
)
def frota_diaria():
    # retentativas cobrem a primeira subida, quando a ANP ainda não foi carregada
    @task(outlets=[FROTA_ABASTECIMENTOS], retries=3, retry_delay=timedelta(minutes=15))
    def gerar(dag_run=None) -> int:
        from pipeline import db, frota

        # run_after existe também em execuções manuais (no Airflow 3 elas não têm logical_date)
        dia = (dag_run.run_after.astimezone(FUSO) - timedelta(days=1)).date()
        with db.conectar() as conn:
            return frota.carregar(conn, dia, dia)

    gerar()


frota_diaria()
