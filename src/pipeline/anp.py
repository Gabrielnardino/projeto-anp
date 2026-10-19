"""Coleta da Série Histórica de Preços de Combustíveis da ANP (diesel + GNV, arquivos mensais).

Uso: python -m pipeline.anp [AAAA-MM-DD]   # sincroniza da data informada até hoje
"""

import csv
import io
import logging
import sys
from datetime import date

import httpx
import psycopg

from pipeline import db

log = logging.getLogger(__name__)

BASE_URL = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsan"
# A ANP muda o nome do arquivo de um mês para outro, então tentamos todos os padrões já vistos.
PADROES_ARQUIVO = (
    "{ano}/precos-diesel-gnv-{mes:02d}.csv",
    "{ano}/{mes:02d}-dados-abertos-precos-diesel-gnv.csv",
    "{ano}/{mes:02d}-dados-abertos-precos-{ano}-{mes:02d}-diesel-gnv.csv",
    "{ano}/{mes:02d}-dados-abertos-precos-diesel-gnv",
)
CABECALHO = [
    "Regiao - Sigla", "Estado - Sigla", "Municipio", "Revenda", "CNPJ da Revenda",
    "Nome da Rua", "Numero Rua", "Complemento", "Bairro", "Cep", "Produto",
    "Data da Coleta", "Valor de Venda", "Valor de Compra", "Unidade de Medida", "Bandeira",
]  # fmt: skip
INICIO_SERIE = date(2024, 1, 1)
MESES_RECARREGADOS = 2  # a ANP às vezes republica os meses mais recentes


def baixar(competencia: date, cliente: httpx.Client) -> str | None:
    """Texto do CSV do mês, ou None se a ANP ainda não publicou."""
    for padrao in PADROES_ARQUIVO:
        url = f"{BASE_URL}/{padrao.format(ano=competencia.year, mes=competencia.month)}"
        resp = cliente.get(url)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        log.info("baixado %s (%d bytes)", url, len(resp.content))
        return resp.content.decode("utf-8-sig")
    return None


def parsear(texto: str) -> list[list[str]]:
    """Valida o layout e devolve as linhas. Falha alto se a ANP mudar o arquivo."""
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=";")
    cabecalho = next(leitor, None)
    if cabecalho != CABECALHO:
        raise ValueError(f"Layout do arquivo da ANP mudou: {cabecalho}")
    linhas = []
    for n, linha in enumerate(leitor, start=2):
        if not linha:
            continue
        if len(linha) != len(CABECALHO):
            raise ValueError(f"Linha {n} com {len(linha)} colunas: {linha}")
        linhas.append(linha)
    return linhas


def carregar(conn: psycopg.Connection, competencia: date, linhas: list[list[str]]) -> None:
    """Substitui a competência inteira (idempotente)."""
    colunas = (
        "competencia, regiao, uf, municipio, revenda, cnpj, nome_rua, numero_rua, complemento, "
        "bairro, cep, produto, data_coleta, valor_venda, valor_compra, unidade_medida, bandeira"
    )
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("delete from raw.anp_precos where competencia = %s", (competencia,))
        with cur.copy(f"copy raw.anp_precos ({colunas}) from stdin") as copy:
            for linha in linhas:
                copy.write_row([competencia, *linha])
    log.info("competência %s: %d linhas", competencia, len(linhas))


def meses(inicio: date, fim: date) -> list[date]:
    atual, saida = inicio.replace(day=1), []
    while atual <= fim:
        saida.append(atual)
        atual = date(atual.year + atual.month // 12, atual.month % 12 + 1, 1)
    return saida


def sincronizar(inicio: date = INICIO_SERIE, hoje: date | None = None) -> list[date]:
    """Carrega meses que faltam e recarrega os mais recentes. Devolve as competências carregadas."""
    todos = meses(inicio, hoje or date.today())
    recentes = set(todos[-(MESES_RECARREGADOS + 1) :])
    carregadas = []
    with db.conectar() as conn, httpx.Client(timeout=120, follow_redirects=True) as cliente:
        existentes = {r[0] for r in conn.execute("select distinct competencia from raw.anp_precos")}
        for competencia in todos:
            if competencia in existentes and competencia not in recentes:
                continue
            texto = baixar(competencia, cliente)
            if texto is None:
                log.info("competência %s ainda não publicada", competencia)
                continue
            carregar(conn, competencia, parsear(texto))
            carregadas.append(competencia)
    return carregadas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    inicio = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else INICIO_SERIE
    print(sincronizar(inicio))
