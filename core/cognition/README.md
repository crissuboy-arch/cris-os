# 🧠 core/cognition/ — Camada de Inteligência Estratégica

Evolui o CRIS OS de "sistema de agentes" para **sistema operacional autônomo**,
inserindo um ciclo de raciocínio **acima** da execução de agentes.

## O pipeline autônomo
```
Objetivo da Cris
  → StrategicPlanner   pensa: contexto + memória (4 camadas) + estratégia → Plano
  → ExecutionManager   executa: distribui, monitora, reexecuta, timeout → Relatório
  → QualitySupervisor  avalia: objetivo atingido? aprova OU pede refação
        ↑________________ loop de re-execução (até max_revisions) ________________|
  → (aprovado) → ResponseComposer → Cris
```

## Os três componentes (uma responsabilidade cada — SRP)
| Componente | Faz | NÃO faz |
|---|---|---|
| **StrategicPlanner** | pensa, escolhe estratégia, cria o plano | executar |
| **ExecutionManager** | distribui, monitora, reexecuta, controla timeout | decidir estratégia |
| **QualitySupervisor** | avalia qualidade, aprova ou pede refação | falar com a Cris |

## Relação com o pipeline v3
- O **IntentRouter** vira uma peça que o Planner pode usar para escolher o agente de cada passo.
- O **WorkflowEngine** continua despachando o agente e persistindo a Task; o **ExecutionManager** é a gerência em volta (retentativa/timeout/monitoramento).
- O **ResponseComposer** é reaproveitado para a entrega final.

## Event Bus
Todos usam o Event Bus existente. Novos eventos em
[core/domain/events.py](../domain/events.py): `objective.received`,
`context.analyzed`, `strategy.selected`, `plan.created`, `execution.started`,
`execution.progress`, `task.retried`, `task.timeout`, `execution.completed`,
`quality.evaluated`, `quality.approved`, `quality.rejected`, `reexecution.requested`.

## ⚠️ Status: ARQUITETURA, sem funcionalidade
- ✅ Domínio (`core/domain/planning.py`), portas (`core/contracts/cognition.py`),
  eventos e esqueletos prontos.
- ✅ Os componentes são **construídos** no runtime (fazem parte da arquitetura
  principal), mas a camada está **inativa**: o `plan()/execute()/review()`
  levantam `NotImplementedError`.
- 🔴 A inteligência será implementada **após a próxima revisão de arquitetura**.
- O atendimento à Cris segue pelo pipeline v3 (`core/application/Orchestrator`)
  até a ativação.
