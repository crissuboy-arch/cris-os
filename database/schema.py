"""
Schema do banco SQLite do CRIS OS.

Cria todas as tabelas automaticamente na primeira execucao.
"""

import logging

from database.connection import get_connection

logger = logging.getLogger(__name__)

SCHEMA_SQL = """

CREATE TABLE IF NOT EXISTS conversas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    papel       TEXT NOT NULL DEFAULT 'user',
    conteudo    TEXT NOT NULL,
    agente      TEXT DEFAULT NULL,
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preferencias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    chave       TEXT NOT NULL,
    valor       TEXT NOT NULL,
    UNIQUE(usuario_id, chave)
);

CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    nome        TEXT NOT NULL,
    empresa     TEXT DEFAULT '',
    telefone    TEXT DEFAULT '',
    email       TEXT DEFAULT '',
    observacoes TEXT DEFAULT '',
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projetos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    nome        TEXT NOT NULL,
    descricao   TEXT DEFAULT '',
    status      TEXT DEFAULT 'ativo',
    contexto    TEXT DEFAULT '',
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tarefas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      TEXT NOT NULL,
    titulo          TEXT NOT NULL,
    descricao       TEXT DEFAULT '',
    prioridade      TEXT DEFAULT 'media',
    prazo           TEXT DEFAULT '',
    responsavel     TEXT DEFAULT '',
    agente          TEXT DEFAULT '',
    status          TEXT DEFAULT 'pendente',
    projeto_id      INTEGER DEFAULT NULL,
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lembretes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      TEXT NOT NULL,
    titulo          TEXT NOT NULL,
    data_hora       TEXT NOT NULL,
    recorrencia     TEXT DEFAULT '',
    tarefa_id       INTEGER DEFAULT NULL,
    status          TEXT DEFAULT 'ativo',
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tarefa_id) REFERENCES tarefas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS prompts_favoritos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    conteudo    TEXT NOT NULL,
    categoria   TEXT DEFAULT '',
    favorito    INTEGER DEFAULT 0,
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS configuracoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    chave       TEXT NOT NULL,
    valor       TEXT NOT NULL,
    UNIQUE(usuario_id, chave)
);

CREATE TABLE IF NOT EXISTS logs_atividade (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      TEXT DEFAULT '',
    agente          TEXT DEFAULT '',
    ferramenta      TEXT DEFAULT '',
    modelo          TEXT DEFAULT '',
    duracao_ms      INTEGER DEFAULT 0,
    erro            TEXT DEFAULT '',
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contexto_recente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    chave       TEXT NOT NULL,
    valor       TEXT NOT NULL,
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(usuario_id, chave)
);

CREATE TABLE IF NOT EXISTS contexto_permanente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    chave       TEXT NOT NULL,
    valor       TEXT NOT NULL,
    UNIQUE(usuario_id, chave)
);

CREATE TABLE IF NOT EXISTS objetivos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      TEXT NOT NULL,
    objetivo        TEXT NOT NULL,
    tipo            TEXT DEFAULT 'geral',
    projeto_id      INTEGER DEFAULT NULL,
    plano           TEXT DEFAULT '{}',
    status          TEXT DEFAULT 'planejado',
    criado_em       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dependencias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL,
    tarefa_id   INTEGER NOT NULL,
    depende_de  INTEGER NOT NULL,
    FOREIGN KEY (tarefa_id) REFERENCES tarefas(id) ON DELETE CASCADE,
    FOREIGN KEY (depende_de) REFERENCES tarefas(id) ON DELETE CASCADE
);
"""

TABELAS = [
    "conversas", "preferencias", "clientes", "projetos",
    "tarefas", "lembretes", "prompts_favoritos", "configuracoes",
    "logs_atividade", "contexto_recente", "contexto_permanente",
    "objetivos", "dependencias",
]


def _colunas(conn, tabela: str) -> list[str]:
    cur = conn.execute(f"PRAGMA table_info({tabela})")
    return [r[1] for r in cur.fetchall()]


def migrar() -> list[str]:
    """Aplica migracoes incrementais em bancos existentes."""
    conn = get_connection()
    aplicadas = []

    cols = _colunas(conn, "tarefas")
    if "agente" not in cols:
        conn.execute("ALTER TABLE tarefas ADD COLUMN agente TEXT DEFAULT ''")
        aplicadas.append("tarefas.agente")

    conn.commit()
    if aplicadas:
        logger.info("Migracoes aplicadas: %s", ", ".join(aplicadas))
    return aplicadas


def criar_tabelas() -> list[str]:
    """Cria todas as tabelas. Retorna lista das tabelas criadas."""
    conn = get_connection()
    for statement in SCHEMA_SQL.split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    migrar()
    logger.info("Tabelas criadas/verificadas: %s", ", ".join(TABELAS))
    return TABELAS
