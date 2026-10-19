from datetime import datetime

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag
from ativos import ANP_PRECOS, FROTA_ABASTECIMENTOS

DBT = "/home/airflow/dbt/bin/dbt --no-use-colors {} --project-dir /opt/projeto/dbt"


@dag(
    schedule=(ANP_PRECOS | FROTA_ABASTECIMENTOS),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,  # dbt deps recria dbt_packages; execuções paralelas se atropelam
    tags=["dbt", "transformacao"],
    doc_md="Roda o dbt (modelos + testes) sempre que a ANP ou a frota recebem dados novos.",
)
def transformacao_dbt():
    deps = BashOperator(task_id="dbt_deps", bash_command=DBT.format("deps"))
    # frescor atrasado gera aviso; só falha se a ANP passar de 75 dias sem dados
    frescor = BashOperator(task_id="dbt_frescor", bash_command=DBT.format("source freshness"))
    build = BashOperator(task_id="dbt_build", bash_command=DBT.format("build"))
    deps >> frescor >> build


transformacao_dbt()
