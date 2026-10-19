"""Carrega a amostra real da ANP (set/2026) e um mês de frota. Usado no CI e no dbt docs."""

from datetime import date
from pathlib import Path

from pipeline import anp, db, frota

AMOSTRA = Path(__file__).parent / "fixtures" / "anp_2026_09_amostra.csv"

with db.conectar() as conn:
    anp.carregar(conn, date(2026, 9, 1), anp.parsear(AMOSTRA.read_text(encoding="utf-8-sig")))
    print(frota.carregar(conn, date(2026, 9, 1), date(2026, 9, 30)), "abastecimentos")
