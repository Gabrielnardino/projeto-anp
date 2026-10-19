from datetime import date

import httpx
import pytest

from pipeline import anp

CABECALHO = ";".join(anp.CABECALHO)
LINHA = (
    'S;RS;PORTO ALEGRE;ABASTECEDORA E GARAGEM"SS"LTDA; 90.212.093/0001-00;RUA X;850;;'
    "SANTANA;90640-000;DIESEL S10;18/01/2024;5,99;;R$ / litro;RAIZEN"
)


def test_parsear_aceita_aspas_no_meio_do_campo():
    linhas = anp.parsear(f"{CABECALHO}\r\n{LINHA}\r\n\r\n")
    assert len(linhas) == 1
    assert linhas[0][3] == 'ABASTECEDORA E GARAGEM"SS"LTDA'
    assert linhas[0][12] == "5,99"


def test_parsear_falha_se_layout_mudar():
    with pytest.raises(ValueError, match="Layout"):
        anp.parsear(CABECALHO.replace("Bandeira", "Distribuidora") + "\n")


def test_parsear_falha_em_linha_quebrada():
    with pytest.raises(ValueError, match="Linha 2"):
        anp.parsear(f"{CABECALHO}\nS;RS;PORTO ALEGRE\n")


def test_baixar_tenta_padroes_ate_achar():
    pedidos = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidos.append(req.url.path)
        if req.url.path.endswith("06-dados-abertos-precos-2026-06-diesel-gnv.csv"):
            return httpx.Response(200, content=("﻿" + CABECALHO).encode())
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        texto = anp.baixar(date(2026, 6, 1), cliente)
    assert texto == CABECALHO  # BOM removido
    assert len(pedidos) == 3


def test_baixar_devolve_none_quando_nao_publicado():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as cliente:
        assert anp.baixar(date(2030, 1, 1), cliente) is None


def test_meses_vira_o_ano():
    assert anp.meses(date(2024, 11, 15), date(2025, 2, 1)) == [
        date(2024, 11, 1), date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1),
    ]  # fmt: skip
