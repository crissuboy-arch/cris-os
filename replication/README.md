# 🔁 replication/ — Segunda máquina (replicação + failover)

Estratégia aprovada: **enviar o Event Log + eleição de líder por lease**.

## Como funciona (desenho)
1. **Outbox**: todo evento publicado é gravado no Event Log e marcado no `outbox`
   ([storage/sqlite_ops.py](../storage/sqlite_ops.py)).
2. **Replicator** ([core/contracts/replication.py](../core/contracts/replication.py)):
   um loop periódico lê `pending_outbox()`, envia via `ship()` e confirma com
   `ack_outbox()`. A réplica **reprocessa** os eventos e reconstrói o estado.
3. **Lease** (eleição de líder): cada nó tenta `acquire(owner, ttl)`. Só o líder
   age. Se o líder cair e o lease expirar, o standby assume — **failover**.
4. **Snapshots**: periodicamente, um dump do estado + truncamento do log antigo.

## Status
- ✅ Outbox e lease já persistidos (SQLite).
- ✅ Porta `Replicator` + `NoopReplicator` (drena o outbox localmente).
- 🔴 Envio real entre máquinas (HTTP/arquivo) — próxima fase.
- 🔴 Loop de replicação + promoção automática do standby — próxima fase.

## Backends de estado (todos atrás das mesmas portas)
- **SQLite** (hoje) → cópia simples + snapshots.
- **SQLite + Litestream** → streaming contínuo do arquivo.
- **PostgreSQL** → replicação lógica para multi-nó robusto.

> A decisão-chave já está tomada: **todo estado vive atrás de portas** (memória,
> event log, tasks, lease). Por isso trocar o mecanismo de replicação não toca no
> núcleo.
