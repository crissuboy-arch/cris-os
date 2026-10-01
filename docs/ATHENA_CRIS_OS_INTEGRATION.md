# Integração Cris OS → Athena (executor ATHENA)

Status: adapter REAL implementado (aditivo). Despacho só acontece com `ATHENA_BRIDGE_TOKEN` configurado.

## Papéis

| Sistema | Papel |
|---|---|
| ScalaFlow | inteligência de mercado (origem do `handoff_id`) |
| Cris OS | orquestrador central: cria `ProductionWorkOrder`s e despacha pelo `ExecutorAdapter` |
| Athena/Hermes | executor `ATHENA`: recebe a ordem, roda a missão (skills, revisor) e devolve o resultado |

## Transporte

Ponte HTTP **local** da Athena (somente `127.0.0.1`), mesmo padrão do PageForge (Bearer token). O usuário `crisos` nunca acessa os arquivos da Athena.

```
POST {ATHENA_BRIDGE_URL}/v1/ordens                 {"work_order": <ProductionWorkOrder inteira>}
GET  {ATHENA_BRIDGE_URL}/v1/ordens/{work_order_id}
Authorization: Bearer <ATHENA_BRIDGE_TOKEN>        Idempotency-Key: <work_order_id>
```

Configuração (`config/settings.py`): `ATHENA_BRIDGE_URL` (padrão `http://127.0.0.1:8765`), `ATHENA_BRIDGE_TOKEN` (vazio = nunca despacha), `ATHENA_TIMEOUT` (15 s).

## Identidade

- `work_order_id` = identidade da missão na Athena (idempotência: reenvio/retry da mesma ordem não cria outra missão).
- `handoff_id` = correlação com a origem, preservado de ponta a ponta; várias ordens do mesmo handoff viram várias missões.

## Estados (Athena → Cris OS)

| Athena | Cris OS |
|---|---|
| RECEBIDA, VALIDANDO, PLANEJANDO | DISPATCHED |
| EXECUTANDO, REVISAO, CORRIGINDO | RUNNING |
| AGUARDANDO_HUMANO | WAITING_APPROVAL |
| CONCLUIDA (com artefato) | COMPLETED |
| FALHOU | FAILED |
| CANCELADA | CANCELLED |

O status bruto fica em `metadata["athena_status"]` e o id da missão em `metadata["athena_mission_id"]`. `COMPLETED` só com `output_refs` (gate `pode_marcar_completed`); referências chegam como `athena:<caminho>`.

## Asset types aceitos pela Athena

`LANDING_PAGE` → CRIAR_LANDING_PAGE · `CAROUSEL`/`MARKETING_MATERIAL` → CRIAR_CRIATIVO · `EBOOK` → CRIAR_COPY.
Recusados (FAILED com motivo): `APP`, `CRM`, `DISTRIBUTION` (publicação é ação crítica), `UNKNOWN`.
`metadata.athena_mission_type` pode fixar o tipo de missão (ex.: `ANALISAR_OFERTA`).

## Erros

rede / 429 / 5xx → transitório (status inalterado, retry pelo Production Runner) · 401/403, 409, 422/4xx → `FAILED` permanente com motivo em `last_error` (token nunca exposto).

## Roteamento e Production Runner

A tabela fixa `core/production_router.py` **não** envia nenhum asset para `ATHENA`. Só ordens com `executor_type="ATHENA"` definido explicitamente chegam à Athena. Com `PRODUCTION_RUNNER_ENABLED=True` e token configurado, essas ordens `READY` são despachadas automaticamente pelo runner (após reinício do `cris-os-bot`). Mudar o roteamento fixo é decisão de negócio separada.

## Segurança

Uma ordem de produção nunca dispara ação crítica na Athena (publicar, gastar, campanha, envio em massa): do lado da Athena isso exige checkpoint humano da Cristiane + trava.

Arquivos: `core/athena_adapter.py`, `tests/test_athena_adapter.py`; aditivos em `core/executor_adapter.py`, `memory/project_brain.py`, `config/settings.py`.
