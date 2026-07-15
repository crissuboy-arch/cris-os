"""
SQLiteOpsStore — estado OPERACIONAL em SQLite, num único adaptador coeso:

  - Event Log (append-only)         -> EventLog
  - Outbox (eventos a replicar)     -> base da replicação
  - Tasks (ciclo de vida)           -> TaskStore
  - Lease (eleição de líder)        -> LeaseStore

Tudo que é necessário para AUDITORIA, REPLICAÇÃO e FAILOVER vive aqui, separado
da memória (sqlite_memory.py) por responsabilidade. Conexão própria com WAL +
lock para uso concorrente (o canal chama o núcleo em outra thread).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from core.domain.events import Event
from core.models import Task
from storage._base import SQLiteStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    id             TEXT NOT NULL,
    type           TEXT NOT NULL,
    payload        TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    source         TEXT NOT NULL,
    ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_corr ON events(correlation_id);

CREATE TABLE IF NOT EXISTS outbox (
    seq     INTEGER PRIMARY KEY,
    shipped INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    instruction TEXT NOT NULL,
    status      TEXT NOT NULL,
    result      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS lease (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    owner      TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SQLiteOpsStore(SQLiteStore):
    """Implementa EventLog, TaskStore e LeaseStore (+ outbox de replicação)."""

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # EventLog (+ outbox)
    # ------------------------------------------------------------------
    def append(self, event: Event) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events(id, type, payload, correlation_id, source, ts) "
                "VALUES (?,?,?,?,?,?)",
                (
                    event.id,
                    event.type,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.correlation_id,
                    event.source,
                    event.ts,
                ),
            )
            seq = int(cur.lastrowid)
            self._conn.execute("INSERT INTO outbox(seq, shipped) VALUES (?, 0)", (seq,))
            self._conn.commit()
        return seq

    def read_since(self, cursor: int = 0, limit: int = 500) -> list[tuple[int, Event]]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT * FROM events WHERE seq > ? ORDER BY seq LIMIT ?",
                (cursor, limit),
            ).fetchall()
        return [(r["seq"], self._linha_para_event(r)) for r in linhas]

    @staticmethod
    def _linha_para_event(r: sqlite3.Row) -> Event:
        return Event(
            id=r["id"],
            type=r["type"],
            payload=json.loads(r["payload"]) if r["payload"] else {},
            correlation_id=r["correlation_id"],
            source=r["source"],
            ts=r["ts"],
        )

    # --- Outbox (para o Replicator enviar à 2ª máquina) ---
    def pending_outbox(self, limit: int = 500) -> list[tuple[int, Event]]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT e.* FROM outbox o JOIN events e ON e.seq = o.seq "
                "WHERE o.shipped = 0 ORDER BY o.seq LIMIT ?",
                (limit,),
            ).fetchall()
        return [(r["seq"], self._linha_para_event(r)) for r in linhas]

    def ack_outbox(self, up_to_seq: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE outbox SET shipped = 1 WHERE seq <= ?", (up_to_seq,)
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # TaskStore
    # ------------------------------------------------------------------
    def save(self, task: Task) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks"
                "(id, agent, instruction, status, result, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (task.id, task.agent, task.instruction, task.status,
                 task.result, task.created_at, task.updated_at),
            )
            self._conn.commit()

    def update(self, task: Task) -> None:
        self.save(task)

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._linha_para_task(r) if r else None

    def list_by_status(self, status: str) -> list[Task]:
        with self._lock:
            linhas = self._conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY created_at", (status,)
            ).fetchall()
        return [self._linha_para_task(r) for r in linhas]

    @staticmethod
    def _linha_para_task(r: sqlite3.Row) -> Task:
        return Task(
            id=r["id"], agent=r["agent"], instruction=r["instruction"],
            status=r["status"], result=r["result"],
            created_at=r["created_at"], updated_at=r["updated_at"],
        )

    # ------------------------------------------------------------------
    # LeaseStore (eleição de líder p/ 2ª máquina)
    # ------------------------------------------------------------------
    def acquire(self, owner: str, ttl_seconds: int) -> bool:
        agora = _now()
        novo_exp = (agora + timedelta(seconds=ttl_seconds)).isoformat()
        with self._lock:
            r = self._conn.execute("SELECT owner, expires_at FROM lease WHERE id=1").fetchone()
            livre = (
                r is None
                or r["owner"] == owner
                or datetime.fromisoformat(r["expires_at"]) < agora
            )
            if not livre:
                return False
            self._conn.execute(
                "INSERT OR REPLACE INTO lease(id, owner, expires_at) VALUES (1, ?, ?)",
                (owner, novo_exp),
            )
            self._conn.commit()
            return True

    def renew(self, owner: str, ttl_seconds: int) -> bool:
        return self.acquire(owner, ttl_seconds)

    def current(self):
        from core.contracts.replication import Lease

        with self._lock:
            r = self._conn.execute("SELECT owner, expires_at FROM lease WHERE id=1").fetchone()
        return Lease(owner=r["owner"], expires_at=r["expires_at"]) if r else None
