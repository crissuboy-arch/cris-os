"""
Executor Adapter -- interface comum que QUALQUER executor especializado
futuro (PageForge, Pink Logic, Criador-de-App, ForgeHub, NEXORA) implementará
para receber trabalho do Cris OS.

NENHUM adapter real existe nesta fase -- nenhuma chamada HTTP, nenhuma
integração com API externa. Este módulo só define o CONTRATO (Protocol) e
um único stub seguro (`AdapterNaoConectado`) que PROVA a forma do contrato
sem nunca fingir produção concluída.

Quando um executor real for conectado (fase futura, fora desta missão):
  1. Implementar `ExecutorAdapter` para aquele executor específico.
  2. Registrar em `EXECUTOR_REGISTRY[<executor_type>]`.
  3. `core/production_orders.py` (ou quem despachar) passa a encontrar um
     adapter real em vez do stub -- nenhuma mudança de contrato necessária.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from memory.project_brain import ProductionWorkOrder


@runtime_checkable
class ExecutorAdapter(Protocol):
    """Contrato que todo executor especializado deve implementar."""

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        """True se este adapter sabe processar `work_order.executor_type`."""
        ...

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Envia a WorkOrder para o executor real. Só um adapter REAL pode
        avançar `status` para `DISPATCHED` -- nunca o stub."""
        ...

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        """Consulta o status atual no executor (não usado enquanto nenhum
        adapter real existir)."""
        ...

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        """Recolhe o resultado (`output_refs`) quando o executor concluir --
        só marca `COMPLETED` quando há evidência/output real correspondente
        (nunca conclusão sem artefato quando o contrato exige um)."""
        ...


class AdapterNaoConectado:
    """
    Stub seguro (Seção 7 da missão) -- prova a forma do `ExecutorAdapter`
    sem NUNCA fingir produção concluída. `can_handle` sempre responde True
    (aceita classificar qualquer executor_type conhecido), mas `dispatch`
    NUNCA avança o status da WorkOrder -- devolve exatamente a mesma
    WorkOrder, inalterada, porque não há nenhum executor real do outro lado
    para receber o trabalho.
    """

    def can_handle(self, work_order: ProductionWorkOrder) -> bool:
        return True

    def dispatch(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        # NUNCA marca DISPATCHED -- nenhum executor real recebeu isto.
        return work_order

    def get_status(self, work_order: ProductionWorkOrder) -> str:
        return work_order.status

    def collect_result(self, work_order: ProductionWorkOrder) -> ProductionWorkOrder:
        # Nunca inventa um resultado -- sem executor real, não há o que coletar.
        return work_order


# Nenhum executor real registrado nesta fase -- toda chave aponta para o
# MESMO stub seguro. Conectar um executor real = substituir a entrada
# correspondente por uma implementação real de `ExecutorAdapter`.
EXECUTOR_REGISTRY: dict[str, ExecutorAdapter] = {
    "APP_BUILDER": AdapterNaoConectado(),
    "PAGEFORGE": AdapterNaoConectado(),
    "PINK_LOGIC": AdapterNaoConectado(),
    "FORGEHUB": AdapterNaoConectado(),
    "NEXORA": AdapterNaoConectado(),
}


def obter_adapter(executor_type: str) -> ExecutorAdapter | None:
    """Devolve o adapter registrado para este `executor_type`, ou `None`
    quando não há nenhum (ex.: `NEEDS_ROUTING`) -- nunca um adapter padrão
    genérico que finja saber processar qualquer coisa."""
    return EXECUTOR_REGISTRY.get(executor_type)
