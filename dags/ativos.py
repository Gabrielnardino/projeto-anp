"""Assets (Airflow 3) que ligam a ingestão à transformação."""

from airflow.sdk import Asset

ANP_PRECOS = Asset("postgres://postgres:5432/dw/raw/anp_precos")
FROTA_ABASTECIMENTOS = Asset("postgres://postgres:5432/dw/raw/frota_abastecimentos")
