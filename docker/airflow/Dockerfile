FROM apache/airflow:3.3.2-python3.12

# dbt fica num venv separado para não brigar com as dependências do Airflow
RUN python -m venv /home/airflow/dbt \
 && /home/airflow/dbt/bin/pip install --no-cache-dir dbt-core==1.12.6 dbt-postgres==1.11.0

RUN pip install --no-cache-dir "psycopg[binary]==3.3.6"
