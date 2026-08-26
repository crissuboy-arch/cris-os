"""
Testes da migracao idempotente do modulo Prospector (prospector_leads).

Usa um prospector.db ficticio (tempdir) para nao depender da Maquina de Leads
real e garante: criacao da tabela, UPSERT por slug, idempotencia e que
NUNCA apaga dados existentes.
"""

import os
import sqlite3
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from database.connection import get_connection  # noqa: E402
from database.schema import criar_tabelas  # noqa: E402
from services.prospector import migration  # noqa: E402


@pytest.fixture()
def ml_db(tmp_path):
    db = tmp_path / "prospector.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE leads (
            slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT,
            siteAntigo TEXT, status TEXT, nota REAL, avaliacoes INTEGER,
            valor REAL, manutencao REAL, pago INTEGER,
            contratoStatus TEXT, contratoEm TEXT
        )
    """)
    conn.execute("""
        INSERT INTO leads (slug, nome, nicho, cidade, status, valor, contratoStatus)
        VALUES ('loja-1', 'Loja Um', 'impressao 3d', 'Lisboa', 'fechado', 500.0, 'assinado')
    """)
    conn.execute("""
        INSERT INTO leads (slug, nome, nicho, cidade, status)
        VALUES ('loja-2', 'Loja Dois', 'moveis', 'Porto', 'novo')
    """)
    conn.commit()
    conn.close()
    return str(db)


def setup_module():
    criar_tabelas()


def teardown_module():
    conn = get_connection()
    conn.execute("DELETE FROM prospector_leads")
    conn.commit()


def test_migracao_cria_tabela(ml_db):
    migration.criar_tabela()
    conn = get_connection()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(prospector_leads)").fetchall()]
    for c in ("slug", "nome", "nicho", "cidade", "site_antigo", "status",
              "contrato_status", "contrato_em"):
        assert c in cols


def test_sincronizar_insere_upsert(ml_db):
    migration.limpar()
    n = migration.sincronizar(ml_db)
    assert n == 2
    assert migration.contar() == 2

    # Atualiza um lead na origem e sincroniza de novo -> upsert, nao duplica
    src = sqlite3.connect(ml_db)
    src.execute("UPDATE leads SET status='redesenhado' WHERE slug='loja-1'")
    src.commit()
    src.close()
    n2 = migration.sincronizar(ml_db)
    assert n2 == 2
    assert migration.contar() == 2
    lead = migration.listar("redesenhado")
    assert len(lead) == 1 and lead[0]["slug"] == "loja-1"


def test_sincronizar_idempotente(ml_db):
    migration.limpar()
    migration.sincronizar(ml_db)
    migration.sincronizar(ml_db)
    migration.sincronizar(ml_db)
    assert migration.contar() == 2


def test_sincronizar_nunca_apaga(ml_db):
    migration.limpar()
    migration.sincronizar(ml_db)
    assert migration.contar() == 2
    # Removendo o banco de origem, o espelho permanece
    assert migration.sincronizar("/caminho/inexistente/db.db") == 0
    assert migration.contar() == 2


def test_listar_contratos_e_financeiro(ml_db):
    migration.limpar()
    migration.sincronizar(ml_db)
    contratos = migration.listar_contratos()
    assert len(contratos) == 1 and contratos[0]["slug"] == "loja-1"
    resumo = migration.resumo_financeiro()
    assert resumo["fechados"] == 1
    assert resumo["total"] == 500.0
