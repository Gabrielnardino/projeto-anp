"""Gerador determinístico da frota e dos abastecimentos de uma transportadora fictícia.

Os abastecimentos acontecem em postos REAIS da pesquisa da ANP, com o preço praticado
pelo posto. Uma pequena fração recebe anomalias (sobrepreço, desvio de combustível etc.),
registradas em raw.frota_gabarito para medir depois se as regras de auditoria as encontram.

Tudo é função da data: gerar o mesmo dia duas vezes produz exatamente as mesmas linhas.

Uso: python -m pipeline.frota INICIO [FIM]   # datas AAAA-MM-DD; FIM padrão = ontem
"""

import hashlib
import heapq
import logging
import random
import string
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import psycopg

from pipeline import db

log = logging.getLogger(__name__)

SEMENTE = 42
INICIO_OPERACAO = date(2025, 1, 1)
VEICULOS_POR_BASE = 15
MOTORISTAS_POR_BASE = 22

# base: (cidade, UFs atendidas pelas rotas que partem dela)
BASES = {
    "POA": ("PORTO ALEGRE", ["RS", "SC", "PR"]),
    "CPS": ("CAMPINAS", ["SP", "MG", "RJ", "PR"]),
    "GYN": ("GOIANIA", ["GO", "DF", "MG", "MT"]),
    "REC": ("RECIFE", ["PE", "PB", "AL", "BA"]),
}
# (marca, modelo, km/l de referência, tanque em litros)
MODELOS = [
    ("SCANIA", "R 450", 2.4, 600),
    ("VOLVO", "FH 540", 2.3, 600),
    ("MERCEDES-BENZ", "ACTROS 2651", 2.4, 500),
    ("DAF", "XF 530", 2.5, 600),
    ("VOLKSWAGEN", "CONSTELLATION 24.280", 3.0, 400),
    ("IVECO", "TECTOR 240E30", 3.1, 300),
]
NOMES = "ANDERSON ADRIANO CARLOS CLAUDIO EDSON FABIO GILMAR JOAO JOSE LUIZ MARCOS PAULO RAFAEL RODRIGO SERGIO VALDIR WAGNER ROSANA PATRICIA CRISTINA".split()  # noqa: E501
SOBRENOMES = "SILVA SANTOS OLIVEIRA SOUZA LIMA PEREIRA FERREIRA COSTA RODRIGUES ALMEIDA NASCIMENTO CARVALHO GOMES MARTINS ROCHA RIBEIRO BARBOSA".split()  # noqa: E501
# Caminhões fabricados a partir de 2012 (PROCONVE P7) exigem S10; os anteriores usam S500.
# Na pesquisa da ANP o S500 aparece só como "DIESEL".
PRODUTO_ANP = {"DIESEL S10": "DIESEL S10", "DIESEL S500": "DIESEL"}

ANOMALIAS = {  # tipo: peso
    "sobrepreco": 0.30,
    "consumo_anomalo": 0.25,
    "litros_acima_tanque": 0.15,
    "abastecimento_duplicado": 0.15,
    "odometro_regressivo": 0.15,
}
PROB_ANOMALIA = 0.015
PROB_ANOMALIA_PROPENSO = 0.12  # alguns motoristas concentram as fraudes, como na vida real
POSTOS_PREFERENCIAIS = 6


@dataclass(frozen=True)
class Veiculo:
    placa: str
    marca: str
    modelo: str
    ano_fabricacao: int
    capacidade_tanque_l: int
    km_por_litro_ref: float
    produto: str
    base: str
    odometro_inicial: int
    motorista_titular: str


@dataclass(frozen=True)
class Motorista:
    matricula: str
    nome: str
    base: str
    data_admissao: date
    propenso: bool


@dataclass(frozen=True)
class Posto:
    cnpj: str
    uf: str
    produto: str  # nome do produto na ANP
    valor_venda: float


def gerar_frota() -> tuple[list[Veiculo], list[Motorista]]:
    rng = random.Random(SEMENTE)
    veiculos, motoristas = [], []
    for base in BASES:
        da_base = []
        for _ in range(MOTORISTAS_POR_BASE):
            m = Motorista(
                matricula=f"M{len(motoristas) + 1:04d}",
                nome=f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}",
                base=base,
                data_admissao=date(2015, 1, 1) + timedelta(days=rng.randrange(3600)),
                propenso=rng.random() < 0.05,
            )
            motoristas.append(m)
            da_base.append(m)
        for i in range(VEICULOS_POR_BASE):
            marca, modelo, kml, tanque = rng.choice(MODELOS)
            ano = rng.randint(2008, 2024)
            veiculos.append(
                Veiculo(
                    placa=_placa(rng),
                    marca=marca,
                    modelo=modelo,
                    ano_fabricacao=ano,
                    capacidade_tanque_l=tanque,
                    km_por_litro_ref=kml,
                    produto="DIESEL S10" if ano >= 2012 else "DIESEL S500",
                    base=base,
                    odometro_inicial=rng.randint(80_000, 900_000),
                    motorista_titular=da_base[i].matricula,
                )
            )
    return veiculos, motoristas


def _placa(rng: random.Random) -> str:  # padrão Mercosul: ABC1D23
    letras = string.ascii_uppercase
    return (
        "".join(rng.choices(letras, k=3))
        + str(rng.randrange(10))
        + rng.choice(letras)
        + f"{rng.randrange(100):02d}"
    )


def _rng(*partes: object) -> random.Random:
    return random.Random("-".join(map(str, (SEMENTE, *partes))))


def km_do_dia(v: Veiculo, d: date) -> int:
    """Quilômetros rodados no dia (0 = parado)."""
    rng = _rng(v.placa, d, "km")
    if rng.random() > (0.85, 0.85, 0.85, 0.85, 0.85, 0.5, 0.2)[d.weekday()]:
        return 0
    # nunca mais que 90% do tanque num dia, para o abastecimento normal caber no tanque
    teto = int(0.9 * v.capacidade_tanque_l * v.km_por_litro_ref)
    return min(rng.randint(250, 750), teto)


def _opcoes(veiculos: list[Veiculo], postos: list[Posto], d: date) -> dict:
    if not postos:
        raise RuntimeError(f"Sem preços da ANP para {d}; rode a coleta da ANP antes.")
    por_uf_produto = defaultdict(list)
    for p in postos:
        por_uf_produto[p.uf, p.produto].append(p)
    opcoes = {}
    for v in veiculos:
        ufs = BASES[v.base][1]
        elegiveis = [p for uf in ufs for p in por_uf_produto[uf, PRODUTO_ANP[v.produto]]]
        if not elegiveis:
            raise RuntimeError(f"Nenhum posto com {v.produto} em {ufs} em {d}.")

        # rendezvous hashing: os postos conveniados do veículo mudam pouco quando a ANP
        # inclui ou remove postos da pesquisa
        def chave(p: Posto, placa: str = v.placa) -> str:
            return hashlib.sha1(f"{placa}{p.cnpj}".encode()).hexdigest()

        opcoes[v.placa] = (elegiveis, heapq.nsmallest(POSTOS_PREFERENCIAIS, elegiveis, key=chave))
    return opcoes


def simular(
    veiculos: list[Veiculo],
    motoristas: list[Motorista],
    inicio: date,
    fim: date,
    postos_da_semana: Callable[[date], list[Posto]],
) -> tuple[list[tuple], list[tuple]]:
    """Abastecimentos e gabarito de anomalias entre inicio e fim (inclusive).

    postos_da_semana(domingo) devolve os postos com o último preço conhecido até aquele domingo;
    a ANP coleta preços semanalmente, então a consulta é feita uma vez por semana.
    """
    por_matricula = {m.matricula: m for m in motoristas}
    motoristas_da_base = {b: [m for m in motoristas if m.base == b] for b in BASES}
    odometro = {v.placa: v.odometro_inicial for v in veiculos}
    abastecimentos, gabarito = [], []
    semana_atual, opcoes = None, {}  # placa -> (postos elegíveis, postos preferenciais)

    d = INICIO_OPERACAO
    while d <= fim:
        rodando = [(v, km) for v in veiculos if (km := km_do_dia(v, d))]
        for v, km in rodando:
            odometro[v.placa] += km
        if d >= inicio and rodando:
            domingo = d + timedelta(days=6 - d.weekday())
            if domingo != semana_atual:
                semana_atual, opcoes = domingo, _opcoes(veiculos, postos_da_semana(domingo), d)
            for v, km in rodando:
                rng = _rng(v.placa, d, "abastecimento")
                matricula = (
                    v.motorista_titular
                    if rng.random() < 0.8
                    else rng.choice(motoristas_da_base[v.base]).matricula
                )
                elegiveis, preferenciais = opcoes[v.placa]
                posto = rng.choice(preferenciais if rng.random() < 0.75 else elegiveis)
                kml_real = v.km_por_litro_ref * rng.gauss(1, 0.06)
                litros = km / kml_real
                preco = posto.valor_venda * rng.gauss(1, 0.01)
                odo = odometro[v.placa]
                data_hora = datetime(d.year, d.month, d.day, rng.randint(5, 22), rng.randrange(60))
                id_ = f"{v.placa}-{d:%Y%m%d}-1"

                prob = (
                    PROB_ANOMALIA_PROPENSO if por_matricula[matricula].propenso else PROB_ANOMALIA
                )
                tipo = None
                if rng.random() < prob:
                    tipo = rng.choices(list(ANOMALIAS), weights=list(ANOMALIAS.values()))[0]
                if tipo == "sobrepreco":
                    preco *= rng.uniform(1.08, 1.25)
                elif tipo == "consumo_anomalo":
                    litros = min(litros * rng.uniform(1.35, 1.7), v.capacidade_tanque_l * 0.98)
                elif tipo == "litros_acima_tanque":
                    litros = v.capacidade_tanque_l * rng.uniform(1.05, 1.25)
                elif tipo == "odometro_regressivo":
                    odo -= rng.randint(500, 3000)  # erro de digitação; o real segue correto

                linha = _linha(id_, v, matricula, data_hora, posto, litros, preco, odo)
                abastecimentos.append(linha)
                if tipo == "abastecimento_duplicado":
                    # segundo abastecimento minutos depois, no mesmo posto, quase sem rodar
                    id_ = f"{v.placa}-{d:%Y%m%d}-2"
                    abastecimentos.append(
                        _linha(
                            id_, v, matricula,
                            data_hora + timedelta(minutes=rng.randint(10, 50)),
                            posto, rng.uniform(80, 250), preco, odo + rng.randint(0, 3),
                        )
                    )  # fmt: skip
                if tipo:
                    gabarito.append((id_, tipo, d))
        d += timedelta(days=1)
    return abastecimentos, gabarito


def _linha(id_, v, matricula, data_hora, posto, litros, preco, odometro) -> tuple:
    litros, preco = round(litros, 2), round(preco, 2)
    return (
        id_, v.placa, matricula, data_hora, posto.cnpj, v.produto,
        litros, preco, round(litros * preco, 2), odometro,
    )  # fmt: skip


def postos_no_banco(conn: psycopg.Connection) -> Callable[[date], list[Posto]]:
    """Último preço de cada posto/produto coletado pela ANP nos 90 dias até a data.

    90 dias cobrem o atraso de publicação da ANP (~1 mês) para os abastecimentos recentes.
    """

    def consultar(d: date) -> list[Posto]:
        rows = conn.execute(
            """
            select distinct on (cnpj, produto) cnpj, uf, produto, valor_venda
            from (
                select trim(cnpj) as cnpj, uf, produto,
                       replace(valor_venda, ',', '.')::numeric as valor_venda,
                       to_date(data_coleta, 'DD/MM/YYYY') as data_coleta
                from raw.anp_precos
                where competencia >= date_trunc('month', %(d)s::date - 90)
                  and produto in ('DIESEL', 'DIESEL S10')
            ) p
            where data_coleta between %(d)s::date - 90 and %(d)s::date
            order by cnpj, produto, data_coleta desc
            """,
            {"d": d},
        ).fetchall()
        return [Posto(c, uf, prod, float(v)) for c, uf, prod, v in rows]

    return consultar


def carregar(conn: psycopg.Connection, inicio: date, fim: date) -> int:
    """Gera e grava o período, substituindo o que já existir nele (idempotente)."""
    veiculos, motoristas = gerar_frota()
    abastecimentos, gabarito = simular(veiculos, motoristas, inicio, fim, postos_no_banco(conn))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("truncate raw.frota_veiculos, raw.frota_motoristas")
        with cur.copy("copy raw.frota_veiculos from stdin") as copy:
            for v in veiculos:
                copy.write_row(
                    (v.placa, v.marca, v.modelo, v.ano_fabricacao, v.capacidade_tanque_l,
                     v.km_por_litro_ref, v.produto, v.base)
                )  # fmt: skip
        with cur.copy("copy raw.frota_motoristas from stdin") as copy:
            for m in motoristas:
                copy.write_row((m.matricula, m.nome, m.base, m.data_admissao))

        periodo = {"inicio": inicio, "fim": fim + timedelta(days=1)}
        cur.execute(
            "delete from raw.frota_abastecimentos"
            " where data_hora >= %(inicio)s and data_hora < %(fim)s",
            periodo,
        )
        cur.execute(
            "delete from raw.frota_gabarito where data >= %(inicio)s and data < %(fim)s", periodo
        )
        colunas = (
            "id_abastecimento, placa, matricula, data_hora, cnpj_posto, produto,"
            " litros, valor_litro, valor_total, odometro_km"
        )
        with cur.copy(f"copy raw.frota_abastecimentos ({colunas}) from stdin") as copy:
            for linha in abastecimentos:
                copy.write_row(linha)
        with cur.copy("copy raw.frota_gabarito from stdin") as copy:
            for linha in gabarito:
                copy.write_row(linha)
    log.info("%s a %s: %d abastecimentos, %d anomalias", inicio, fim, len(abastecimentos),
             len(gabarito))  # fmt: skip
    return len(abastecimentos)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    inicio = date.fromisoformat(sys.argv[1])
    fim = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today() - timedelta(1)
    with db.conectar() as conn:
        carregar(conn, inicio, fim)
