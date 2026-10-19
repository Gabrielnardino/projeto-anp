"""Conexão com o data warehouse e tabelas da camada raw."""

import os

import psycopg

DSN_PADRAO = "postgresql://dados:dados@localhost:5432/dw"

# Raw da ANP fica como texto: é um arquivo externo e a tipagem acontece no dbt (staging).
# Raw da frota já vem tipado, como viria da exportação de um ERP.
DDL = """
create schema if not exists raw;

create table if not exists raw.anp_precos (
    competencia      date not null,
    regiao           text,
    uf               text,
    municipio        text,
    revenda          text,
    cnpj             text,
    nome_rua         text,
    numero_rua       text,
    complemento      text,
    bairro           text,
    cep              text,
    produto          text,
    data_coleta      text,
    valor_venda      text,
    valor_compra     text,
    unidade_medida   text,
    bandeira         text,
    _carregado_em    timestamptz not null default now()
);
create index if not exists anp_precos_competencia on raw.anp_precos (competencia);

create table if not exists raw.frota_veiculos (
    placa               text primary key,
    marca               text not null,
    modelo              text not null,
    ano_fabricacao      int not null,
    capacidade_tanque_l numeric not null,
    km_por_litro_ref    numeric not null,
    produto             text not null,
    base                text not null
);

create table if not exists raw.frota_motoristas (
    matricula      text primary key,
    nome           text not null,
    base           text not null,
    data_admissao  date not null
);

create table if not exists raw.frota_abastecimentos (
    id_abastecimento  text primary key,
    placa             text not null,
    matricula         text not null,
    data_hora         timestamp not null,
    cnpj_posto        text not null,
    produto           text not null,
    litros            numeric not null,
    valor_litro       numeric not null,
    valor_total       numeric not null,
    odometro_km       int not null,
    _carregado_em     timestamptz not null default now()
);
create index if not exists frota_abastecimentos_data on raw.frota_abastecimentos (data_hora);

create table if not exists raw.frota_gabarito (
    id_abastecimento  text primary key,
    tipo_anomalia     text not null,
    data              date not null
);
"""


def conectar() -> psycopg.Connection:
    conn = psycopg.connect(os.environ.get("DW_DSN", DSN_PADRAO))
    conn.execute(DDL)
    conn.commit()
    return conn
