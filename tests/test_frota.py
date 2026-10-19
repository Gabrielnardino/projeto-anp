from collections import defaultdict
from datetime import date

from pipeline import frota

UFS = {uf for _, ufs in frota.BASES.values() for uf in ufs}
POSTOS = [
    frota.Posto(f"{uf}{i:012d}", uf, produto, 6.0 + i / 100)
    for uf in sorted(UFS)
    for produto in ("DIESEL", "DIESEL S10")
    for i in range(10)
]
INICIO, FIM = date(2025, 3, 1), date(2025, 4, 30)


def _simular():
    veiculos, motoristas = frota.gerar_frota()
    return veiculos, frota.simular(veiculos, motoristas, INICIO, FIM, lambda d: POSTOS)


def test_e_deterministico():
    assert _simular() == _simular()


def test_regras_fisicas_valem_fora_das_anomalias():
    veiculos, (abastecimentos, gabarito) = _simular()
    tanque = {v.placa: v.capacidade_tanque_l for v in veiculos}
    anomalos = {g[0] for g in gabarito}
    por_placa = defaultdict(list)
    for a in abastecimentos:
        id_, placa, *_, litros, preco, total, odometro = a
        assert INICIO <= a[3].date() <= FIM
        assert abs(litros * preco - total) < 0.01
        if id_ not in anomalos:
            assert 0 < litros <= tanque[placa]
            por_placa[placa].append(odometro)
    for odometros in por_placa.values():
        assert odometros == sorted(odometros)


def test_gabarito_aponta_para_abastecimentos_existentes():
    _, (abastecimentos, gabarito) = _simular()
    ids = {a[0] for a in abastecimentos}
    assert gabarito and all(g[0] in ids for g in gabarito)
    assert {g[1] for g in gabarito} <= set(frota.ANOMALIAS)


def test_veiculo_antigo_usa_s500():
    veiculos, _ = frota.gerar_frota()
    assert all((v.produto == "DIESEL S500") == (v.ano_fabricacao < 2012) for v in veiculos)
