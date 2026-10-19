"""Dashboards como código: configura o Metabase e (re)cria os 3 painéis pela API.

Uso: python metabase/provisionar.py   (com o docker compose de pé)
Reexecutar recria os painéis: tudo vive numa coleção própria, que é limpa antes.
"""

import os
import time

import httpx

MB_URL = os.environ.get("MB_URL", "http://localhost:3000")
ADMIN = {
    "email": os.environ.get("MB_ADMIN_EMAIL", "admin@anp-frota.local"),
    "password": os.environ.get("MB_ADMIN_PASSWORD", "Painel#ANP2026"),
}
DW = {
    "host": "postgres",  # nome do serviço no docker compose
    "port": 5432,
    "dbname": "dw",
    "user": os.environ.get("POSTGRES_USER", "dados"),
    "password": os.environ.get("POSTGRES_PASSWORD", "dados"),
    "schema-filters-type": "inclusion",
    "schema-filters-patterns": "marts",
}
COLECAO = "Projeto ANP × Frota"


def linha(x, y, serie=None):
    dims = [x, serie] if serie else [x]
    return {"graph.dimensions": dims, "graph.metrics": [y], "graph.y_axis.unpin_from_zero": True}


# Cada painel: lista de (título, tipo, SQL, configurações, largura, altura). Grade de 24 colunas.
PAINEIS = {
    "1. Mercado de diesel (ANP)": [
        (
            "Diesel S10 — preço médio na última semana",
            "scalar",
            """
            select round(avg(preco_medio), 2) as preco
            from marts.fct_preco_anp_semanal
            where produto = 'DIESEL S10'
              and semana = (select max(semana) from marts.fct_preco_anp_semanal)
        """,
            {"scalar.prefix": "R$ "},
            8,
            4,
        ),
        (
            "Postos pesquisados na última semana",
            "scalar",
            """
            select count(distinct cnpj) as postos
            from marts.fct_preco_anp_semanal
            where semana = (select max(semana) from marts.fct_preco_anp_semanal)
        """,
            {},
            8,
            4,
        ),
        (
            "Spread S10 − S500 (R$/l)",
            "scalar",
            """
            select round(avg(preco_medio) filter (where produto = 'DIESEL S10')
                       - avg(preco_medio) filter (where produto = 'DIESEL S500'), 3) as spread
            from marts.fct_preco_anp_semanal
            where semana = (select max(semana) from marts.fct_preco_anp_semanal)
        """,
            {"scalar.prefix": "R$ "},
            8,
            4,
        ),
        (
            "Preço médio semanal no Brasil",
            "line",
            """
            select semana, produto, round(avg(preco_medio), 3) as preco
            from marts.fct_preco_anp_semanal
            where produto like 'DIESEL%'
            group by 1, 2 order by 1
        """,
            linha("semana", "preco", "produto"),
            24,
            7,
        ),
        (
            "Diesel S10 nas UFs das rotas vs. média nacional (R$/l) — último mês",
            "row",
            """
            with mes as (
                select uf, preco_medio from marts.fct_preco_anp_semanal
                where produto = 'DIESEL S10'
                  and semana >= (select max(semana) - 28 from marts.fct_preco_anp_semanal)
            )
            select uf, round(avg(preco_medio) - (select avg(preco_medio) from mes), 3)
                as diferenca
            from mes
            where uf in ('RS','SC','PR','SP','MG','RJ','GO','DF','MT','PE','PB','AL','BA')
            group by 1 order by 2 desc
        """,
            linha("uf", "diferenca"),
            12,
            10,
        ),
        (
            "Diesel S10 por bandeira vs. média nacional (R$/l) — 12 semanas",
            "row",
            """
            with periodo as (
                select bandeira, cnpj, preco_medio from marts.fct_preco_anp_semanal
                where produto = 'DIESEL S10'
                  and semana >= (select max(semana) - 84 from marts.fct_preco_anp_semanal)
            )
            select bandeira,
                   round(avg(preco_medio) - (select avg(preco_medio) from periodo), 3)
                       as diferenca
            from periodo group by 1 having count(distinct cnpj) >= 50 order by 2 desc
        """,
            linha("bandeira", "diferenca"),
            12,
            10,
        ),
    ],
    "2. Custo e consumo da frota": [
        (
            "Gasto com diesel — últimos 12 meses",
            "scalar",
            """
            select sum(valor_total) as gasto from marts.mart_frota_mensal
            where mes >= date_trunc('month', current_date) - interval '12 months'
        """,
            {"scalar.prefix": "R$ ", "scalar.compact_primary_number": True},
            6,
            4,
        ),
        (
            "km rodados — últimos 12 meses",
            "scalar",
            """
            select sum(km_rodados) as km from marts.mart_frota_mensal
            where mes >= date_trunc('month', current_date) - interval '12 months'
        """,
            {"scalar.compact_primary_number": True},
            6,
            4,
        ),
        (
            "km/l médio da frota",
            "scalar",
            """
            select round(sum(km_rodados) / sum(litros), 2) as km_l from marts.mart_frota_mensal
            where mes >= date_trunc('month', current_date) - interval '12 months'
        """,
            {},
            6,
            4,
        ),
        (
            "Custo por km",
            "scalar",
            """
            select round(sum(valor_total) / sum(km_rodados), 2) as rs_km
            from marts.mart_frota_mensal
            where mes >= date_trunc('month', current_date) - interval '12 months'
        """,
            {"scalar.prefix": "R$ "},
            6,
            4,
        ),
        (
            "Gasto mensal por base",
            "bar",
            """
            select mes, base, round(sum(valor_total)) as gasto
            from marts.mart_frota_mensal group by 1, 2 order by 1
        """,
            {**linha("mes", "gasto", "base"), "stackable.stack_type": "stacked"},
            12,
            8,
        ),
        (
            "Custo por km mensal por base",
            "line",
            """
            select mes, base, round(sum(valor_total) / sum(km_rodados), 3) as custo_por_km
            from marts.mart_frota_mensal group by 1, 2 order by 1
        """,
            linha("mes", "custo_por_km", "base"),
            12,
            8,
        ),
        (
            "Veículos com pior consumo vs. referência — últimos 3 meses",
            "table",
            """
            select placa, base, marca, modelo, km_por_litro_ref as km_l_referencia,
                   round(sum(km_rodados) / sum(litros), 2) as km_l_real,
                   round(100 * (sum(km_rodados) / sum(litros) / km_por_litro_ref - 1), 1)
                       as desvio_pct,
                   sum(abastecimentos_com_alerta) as abastecimentos_com_alerta
            from marts.mart_frota_mensal
            where mes >= date_trunc('month', current_date) - interval '3 months'
            group by 1, 2, 3, 4, 5 order by desvio_pct limit 15
        """,
            {},
            24,
            9,
        ),
    ],
    "3. Auditoria de abastecimentos": [
        (
            "Alertas nos últimos 12 meses",
            "scalar",
            """
            select count(*) as alertas from marts.mart_alertas
            where data >= current_date - interval '12 months'
        """,
            {},
            8,
            4,
        ),
        (
            "Prejuízo estimado dos alertas",
            "scalar",
            """
            select sum(impacto_estimado_rs) as impacto from marts.mart_alertas
            where data >= current_date - interval '12 months'
        """,
            {"scalar.prefix": "R$ ", "scalar.compact_primary_number": True},
            8,
            4,
        ),
        (
            "Pago acima do preço ANP do posto",
            "scalar",
            """
            select sum(pago_acima_anp_rs) as acima from marts.fct_abastecimento
            where data >= current_date - interval '12 months'
        """,
            {"scalar.prefix": "R$ ", "scalar.compact_primary_number": True},
            8,
            4,
        ),
        (
            "Alertas por tipo e mês",
            "bar",
            """
            select date_trunc('month', data)::date as mes, tipo_alerta, count(*) as alertas
            from marts.mart_alertas group by 1, 2 order by 1
        """,
            {**linha("mes", "alertas", "tipo_alerta"), "stackable.stack_type": "stacked"},
            24,
            8,
        ),
        (
            "Motoristas com mais alertas",
            "table",
            """
            select m.matricula, m.nome, m.base, count(*) as alertas,
                   count(distinct a.tipo_alerta) as tipos_distintos,
                   sum(a.impacto_estimado_rs) as impacto_rs
            from marts.mart_alertas a join marts.dim_motorista m using (matricula)
            group by 1, 2, 3 order by alertas desc limit 10
        """,
            {},
            12,
            9,
        ),
        (
            "Postos onde mais se pagou acima da ANP",
            "table",
            """
            select p.revenda, p.bandeira, p.municipio, p.uf, count(*) as abastecimentos,
                   round(100 * avg(f.sobrepreco_pct), 2) as sobrepreco_medio_pct,
                   sum(f.pago_acima_anp_rs) as pago_acima_rs
            from marts.fct_abastecimento f join marts.dim_posto p on p.cnpj = f.cnpj_posto
            group by 1, 2, 3, 4 having sum(f.pago_acima_anp_rs) > 0
            order by pago_acima_rs desc limit 10
        """,
            {},
            12,
            9,
        ),
        (
            "Qualidade das regras (vs. anomalias simuladas)",
            "table",
            """
            select tipo, verdadeiros_positivos, falsos_positivos, falsos_negativos,
                   precisao, recall
            from marts.mart_avaliacao_regras order by tipo
        """,
            {},
            24,
            7,
        ),
    ],
}


def autenticar(mb: httpx.Client) -> None:
    props = mb.get("/api/session/properties").json()
    if not props.get("has-user-setup"):
        resp = mb.post("/api/setup", json={
            "token": props["setup-token"],
            "user": {**ADMIN, "first_name": "Admin", "last_name": "ANP", "site_name": COLECAO},
            "prefs": {"site_name": COLECAO, "allow_tracking": False},
        })  # fmt: skip
    else:
        resp = mb.post(
            "/api/session", json={"username": ADMIN["email"], "password": ADMIN["password"]}
        )
    resp.raise_for_status()
    mb.headers["X-Metabase-Session"] = resp.json()["id"]


def configurar_locale(mb: httpx.Client) -> None:
    mb.put("/api/setting/site-locale", json={"value": "pt_BR"}).raise_for_status()
    mb.put(
        "/api/setting/custom-formatting",
        json={"value": {"type/Number": {"number_separators": ",."}}},
    ).raise_for_status()


def banco_dw(mb: httpx.Client) -> int:
    for banco in mb.get("/api/database").json()["data"]:
        if banco["name"] == "DW":
            return banco["id"]
    resp = mb.post("/api/database", json={"engine": "postgres", "name": "DW", "details": DW})
    resp.raise_for_status()
    return resp.json()["id"]


def colecao_limpa(mb: httpx.Client) -> int:
    for c in mb.get("/api/collection").json():
        if c.get("name") == COLECAO and not c.get("archived"):
            for item in mb.get(f"/api/collection/{c['id']}/items").json()["data"]:
                rota = "card" if item["model"] == "card" else item["model"]
                mb.put(f"/api/{rota}/{item['id']}", json={"archived": True}).raise_for_status()
            return c["id"]
    return mb.post("/api/collection", json={"name": COLECAO}).json()["id"]


def criar_painel(mb, banco, colecao, nome, cartoes) -> None:
    dashcards, col, row, altura_linha = [], 0, 0, 0
    for i, (titulo, tipo, sql, config, largura, altura) in enumerate(cartoes):
        card = mb.post("/api/card", json={
            "name": titulo,
            "display": tipo,
            "collection_id": colecao,
            "visualization_settings": config,
            "dataset_query": {
                "type": "native", "database": banco, "native": {"query": sql.strip()},
            },
        })  # fmt: skip
        card.raise_for_status()
        if col + largura > 24:
            col, row, altura_linha = 0, row + altura_linha, 0
        dashcards.append({
            "id": -(i + 1), "card_id": card.json()["id"],
            "col": col, "row": row, "size_x": largura, "size_y": altura,
        })  # fmt: skip
        col, altura_linha = col + largura, max(altura_linha, altura)
    painel = mb.post("/api/dashboard", json={"name": nome, "collection_id": colecao}).json()
    mb.put(f"/api/dashboard/{painel['id']}", json={"dashcards": dashcards}).raise_for_status()
    print(f"{nome}: http://localhost:3000/dashboard/{painel['id']}")


def main() -> None:
    with httpx.Client(base_url=MB_URL, timeout=300) as mb:
        for _ in range(60):  # o Metabase demora para subir na primeira vez
            try:
                if mb.get("/api/health").json().get("status") == "ok":
                    break
            except httpx.HTTPError:
                pass
            time.sleep(5)
        autenticar(mb)
        configurar_locale(mb)
        banco = banco_dw(mb)
        colecao = colecao_limpa(mb)
        for nome, cartoes in PAINEIS.items():
            criar_painel(mb, banco, colecao, nome, cartoes)


if __name__ == "__main__":
    main()
