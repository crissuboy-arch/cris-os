"""
Migracoes idempotentes do modulo Prospector no banco PRINCIPAL do CRIS OS.

Regras do CRIS OS:
  - Nao criar um segundo banco principal (usa data/cris_os.db).
  - Migrar somente as tabelas necessarias (aqui: `prospector_leads`).
  - Migracoes idempotentes (podem rodar N vezes sem efeito colateral).
  - Nunca apagar dados existentes.

A Maquina de Leads continua com o prospector.db dela (fonte de verdade das
regras). Este modulo apenas espelha os leads no banco do CRIS OS via UPSERT
por slug: insere os novos, atualiza os ja existentes, nunca apaga nada.
"""

from __future__ import annotations

import logging
import os
import sqlite3

from database.connection import get_connection

logger = logging.getLogger(__name__)

TABELA = "prospector_leads"

# Colunas da tabela espelho (snake_case).
CAMPOS = [
    "slug", "nome", "nicho", "cidade", "nota", "avaliacoes", "email",
    "telefone", "whatsapp", "site_antigo", "motivo", "status", "url_nova",
    "data_proposta", "valor", "obs", "contrato_status", "contrato_em",
    "manutencao", "pago", "doc_cliente", "end_cliente", "instagram",
    "ig_seguidores", "ig_posts", "ig_ativo", "ig_categoria", "score",
    "temperatura", "abordagem", "dossie", "busca",
]

# Mapa de colunas da ML (camelCase) -> colunas do CRIS OS (snake_case).
MAP_ML = {
    "slug": "slug", "nome": "nome", "nicho": "nicho", "cidade": "cidade",
    "nota": "nota", "avaliacoes": "avaliacoes", "email": "email",
    "telefone": "telefone", "whatsapp": "whatsapp",
    "siteAntigo": "site_antigo", "motivo": "motivo", "status": "status",
    "urlNova": "url_nova", "dataProposta": "data_proposta", "valor": "valor",
    "obs": "obs", "contratoStatus": "contrato_status",
    "contratoEm": "contrato_em", "manutencao": "manutencao", "pago": "pago",
    "docCliente": "doc_cliente", "endCliente": "end_cliente",
    "instagram": "instagram", "igSeguidores": "ig_seguidores",
    "igPosts": "ig_posts", "igAtivo": "ig_ativo",
    "igCategoria": "ig_categoria", "score": "score",
    "temperatura": "temperatura", "abordagem": "abordagem",
    "dossie": "dossie", "busca": "busca",
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prospector_leads (
    slug            TEXT PRIMARY KEY,
    nome            TEXT,
    nicho           TEXT,
    cidade          TEXT,
    nota            REAL,
    avaliacoes      INTEGER,
    email           TEXT,
    telefone        TEXT,
    whatsapp        TEXT,
    site_antigo     TEXT,
    motivo          TEXT,
    status          TEXT DEFAULT 'novo',
    url_nova        TEXT,
    data_proposta   TEXT,
    valor           REAL,
    obs             TEXT,
    contrato_status TEXT DEFAULT 'pendente',
    contrato_em     TEXT,
    manutencao      REAL,
    pago            INTEGER DEFAULT 0,
    doc_cliente     TEXT,
    end_cliente     TEXT,
    instagram       TEXT,
    ig_seguidores   INTEGER,
    ig_posts        INTEGER,
    ig_ativo        TEXT,
    ig_categoria    TEXT,
    score           INTEGER,
    temperatura     TEXT,
    abordagem       TEXT,
    dossie          TEXT,
    busca           TEXT,
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Tipos das colunas extras (ALTER TABLE ADD COLUMN, idempotente).
TIPOS_EXTRA = {
    "status": "TEXT DEFAULT 'novo'", "contrato_status": "TEXT DEFAULT 'pendente'",
    "ig_seguidores": "INTEGER", "ig_posts": "INTEGER", "ig_ativo": "TEXT",
    "ig_categoria": "TEXT", "score": "INTEGER", "temperatura": "TEXT",
    "abordagem": "TEXT", "dossie": "TEXT", "busca": "TEXT",
    "valor": "REAL", "manutencao": "REAL", "pago": "INTEGER",
}


def _colunas(conn) -> list[str]:
    return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABELA).fetchall()]


def criar_tabela() -> None:
    """Cria a tabela espelho de leads e migra colunas que faltem (idempotente)."""
    conn = get_connection()
    conn.execute(SCHEMA_SQL)
    existentes = _colunas(conn)
    for col, tipo in TIPOS_EXTRA.items():
        if col not in existentes:
            try:
                conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (TABELA, col, tipo))
            except sqlite3.OperationalError:
                pass
    conn.commit()


def _sync_um(conn, lead: dict) -> None:
    """UPSERT de um lead por slug. Nunca apaga; atualiza os ja existentes."""
    valores = {}
    for ml, cr in MAP_ML.items():
        if ml in lead:
            valores[cr] = lead[ml]

    cols = list(valores.keys())
    if not cols:
        return
    if "slug" not in cols:
        valores["slug"] = None
        cols.append("slug")

    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join("%s=excluded.%s" % (c, c) for c in cols if c != "slug")
    sql = (
        "INSERT INTO %s (%s) VALUES (%s) "
        "ON CONFLICT(slug) DO UPDATE SET %s, atualizado_em=CURRENT_TIMESTAMP"
        % (TABELA, ", ".join(cols), placeholders, updates)
    )
    conn.execute(sql, [valores[c] for c in cols])


def sincronizar(ml_db: str | None = None) -> int:
    """Espelha os leads do prospector.db da ML para o banco do CRIS OS.

    Retorna quantos leads foram sincronizados. Idempotente e nunca apaga.
    """
    criar_tabela()
    if ml_db is None:
        from services.prospector.adapter import engine_db
        ml_db = engine_db()

    if not ml_db or not os.path.exists(ml_db):
        return 0

    src = sqlite3.connect(ml_db)
    src.row_factory = sqlite3.Row
    try:
        linhas = [dict(r) for r in src.execute("SELECT * FROM leads")]
    except sqlite3.OperationalError:
        linhas = []
    finally:
        src.close()

    if not linhas:
        return 0

    conn = get_connection()
    for l in linhas:
        _sync_um(conn, l)
    conn.commit()
    logger.info("Prospector: %d leads sincronizados para %s", len(linhas), TABELA)
    return len(linhas)


def listar(status: str | None = None) -> list[dict]:
    """Le leads do banco do CRIS OS (ja sincronizado)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM %s" % TABELA
    params: tuple = ()
    if status:
        sql += " WHERE status=?"
        params = (status,)
    sql += " ORDER BY COALESCE(score,0) DESC, nome"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def contar() -> int:
    conn = get_connection()
    return conn.execute("SELECT COUNT(*) FROM %s" % TABELA).fetchone()[0]


def listar_contratos() -> list[dict]:
    """Leads com contrato gerado/enviado."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    sql = (
        "SELECT * FROM %s "
        "WHERE contrato_em IS NOT NULL AND contrato_em != '' "
        "ORDER BY COALESCE(contrato_em,'') DESC"
    ) % TABELA
    return [dict(r) for r in conn.execute(sql).fetchall()]


def resumo_financeiro() -> dict:
    """Agregado financeiro dos leads (fechados, recebido, a receber, MRR)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    q = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(valor),0) AS total, "
        "COALESCE(SUM(manutencao),0) AS mrr "
        "FROM %s WHERE status='fechado'" % TABELA
    ).fetchone()
    pago = conn.execute(
        "SELECT COALESCE(SUM(valor),0) FROM %s WHERE status='fechado' AND pago>0" % TABELA
    ).fetchone()[0]
    n = q["n"]
    total = q["total"]
    return {
        "fechados": n,
        "total": total,
        "recebido": pago,
        "a_receber": total - pago,
        "mrr": q["mrr"],
        "metas": {},
    }


def limpar() -> None:
    """Usado apenas em testes: apaga o espelho local (nunca toca na ML)."""
    conn = get_connection()
    conn.execute("DELETE FROM %s" % TABELA)
    conn.commit()
