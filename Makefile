EXEC = docker compose exec airflow
DBT_CONTAINER = docker compose exec -w /opt/projeto/dbt airflow /home/airflow/dbt/bin/dbt
DBT = uv run dbt --project-dir dbt --profiles-dir dbt

.PHONY: up down carga-inicial paineis test lint docs

up:  ## sobe Postgres, Airflow (localhost:8080) e Metabase (localhost:3000)
	docker compose up -d --build

down:
	docker compose down

carga-inicial:  ## ANP desde 2024-01, frota desde 2025-01 até ontem, dbt e painéis
	$(EXEC) python -m pipeline.anp
	$(EXEC) python -m pipeline.frota 2025-01-01
	$(DBT_CONTAINER) deps
	$(DBT_CONTAINER) build
	$(MAKE) paineis

paineis:  ## (re)cria os dashboards do Metabase
	docker compose exec -e MB_URL=http://metabase:3000 airflow python /opt/projeto/metabase/provisionar.py

# desenvolvimento local (requer uv)
test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .
	uv run sqlfluff lint dbt

docs:
	$(DBT) docs generate && $(DBT) docs serve --port 8081
